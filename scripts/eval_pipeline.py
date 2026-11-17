"""合成知识库全链路评测。

在 api 容器内运行（需要真实 API、Celery worker 和 embedding Key）：

    python scripts/eval_pipeline.py
    python scripts/eval_pipeline.py --cleanup --strict
    python scripts/eval_pipeline.py --skip-cache --top-k 3

每轮流程：清空评测账号的文档与语义缓存 → 上传固定合成语料并等 ready →
检索层（/rag/search）→ 答案层（/rag/query）→ 缓存层（改写应命中、换实体应拒绝）→
流式层（[DONE] 与 source_chunks 事件）→ 落盘 evaluation/runs/<run_id>/report.{json,md}。

语料固定（evaluation/synth/），跨轮可比；报告记录 git commit、LLM/embedding 模型
和 top_k，缺任何一项都不该拿来横向比较。评测调用会正常写入 llm_call_logs，
便于用定价中心折算本轮成本。
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.llm_call_log import LLMCallLog
from app.models.qa_cache import QACacheEntry
from app.models.user import User
from app.services.llm_service import get_llm_client
from app.services.pricing_service import estimate_cost_cny
from app.services.semantic_cache import (
    _cosine_similarity,
    _embed_query,
    _entity_tokens,
    _numeric_tokens,
    _parse_embedding,
    invalidate_user_cache,
)

BASE_URL = os.getenv("EVAL_BASE_URL", os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000"))
EMAIL = os.getenv("EVAL_EMAIL", "eval-synth@example.com")
USERNAME = os.getenv("EVAL_USERNAME", "eval-synth")
GIT_COMMIT = os.getenv("EVAL_GIT_COMMIT", "unknown")
TIMEOUT = float(os.getenv("EVAL_TIMEOUT", "300"))
RUNS_DIR = Path("evaluation/runs")
CACHE_HIT_PREFIX = "（缓存命中"


class EvalFailure(RuntimeError):
    """基础设施失败：登录、上传、ready 超时等，出现即中止本轮。"""


def _env_value(key: str) -> str:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return ""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


PASSWORD = os.getenv("EVAL_PASSWORD") or _env_value("EVAL_PASSWORD")
if not PASSWORD:
    PASSWORD = os.getenv("SMOKE_PASSWORD") or _env_value("SMOKE_PASSWORD")
if not PASSWORD:
    raise SystemExit("EVAL_PASSWORD 未设置（可复用 SMOKE_PASSWORD，不要写进仓库）")


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise EvalFailure(message)


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _rate(hits: int, total: int) -> float:
    return round(hits / total, 4) if total else 0.0


# ----------------------------- 账号与导入 -----------------------------


def login_or_register(client: httpx.Client) -> str:
    login = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD})
    if login.status_code == 200:
        return login.json()["access_token"]
    if login.status_code != 401:
        raise EvalFailure(f"登录失败: HTTP {login.status_code} {login.text[:200]}")

    created = client.post(
        "/api/v1/users/",
        json={
            "username": USERNAME,
            "email": EMAIL,
            "password": PASSWORD,
            "full_name": "Eval Synth",
        },
    )
    if created.status_code not in (200, 201):
        raise EvalFailure(
            f"评测账号不存在且注册失败: HTTP {created.status_code} {created.text[:200]}"
        )
    login = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD})
    _check(login.status_code == 200, f"注册后登录失败: HTTP {login.status_code}")
    return login.json()["access_token"]


def clear_documents(client: httpx.Client, token: str) -> int:
    response = client.get("/api/v1/rag/documents", headers=_headers(token))
    _check(response.status_code == 200, f"列出文档失败: HTTP {response.status_code}")
    removed = 0
    for doc in response.json():
        deleted = client.delete(f"/api/v1/rag/documents/{doc['id']}", headers=_headers(token))
        if deleted.status_code == 200:
            removed += 1
        else:
            print(f"[WARN] 删除旧文档失败 id={doc['id']}: HTTP {deleted.status_code}")
    return removed


def upload_corpus(client: httpx.Client, token: str, corpus_dir: Path) -> List[Dict[str, Any]]:
    files = sorted(corpus_dir.glob("*.md"))
    _check(bool(files), f"语料目录为空: {corpus_dir}")
    uploaded: List[Dict[str, Any]] = []
    for path in files:
        content = path.read_bytes()
        response = client.post(
            "/api/v1/rag/upload",
            headers=_headers(token),
            files={"file": (path.name, content, "text/markdown")},
        )
        _check(
            response.status_code == 202,
            f"上传 {path.name} 失败: HTTP {response.status_code} {response.text[:200]}",
        )
        uploaded.append(response.json())
    return uploaded


def wait_ready(
    client: httpx.Client, token: str, doc_ids: Sequence[int], timeout: float
) -> Dict[int, Dict[str, Any]]:
    deadline = time.time() + timeout
    pending = set(doc_ids)
    ready: Dict[int, Dict[str, Any]] = {}
    while pending and time.time() < deadline:
        for doc_id in list(pending):
            response = client.get(f"/api/v1/rag/documents/{doc_id}", headers=_headers(token))
            _check(
                response.status_code == 200,
                f"查询文档 {doc_id} 状态失败: HTTP {response.status_code}",
            )
            data = response.json()
            if data["status"] == "ready":
                _check(data["chunks_count"] > 0, f"文档 {doc_id} ready 但 chunks=0")
                ready[doc_id] = data
                pending.discard(doc_id)
            elif data["status"] == "failed":
                raise EvalFailure(f"文档 {doc_id} 处理失败: {data.get('error_message')}")
        if pending:
            time.sleep(2)
    _check(not pending, f"文档处理超时（{timeout:.0f}s）: {sorted(pending)}")
    return ready


# ----------------------------- 判定工具 -----------------------------


def is_cache_hit(answer: str) -> bool:
    return answer.startswith(CACHE_HIT_PREFIX)


def cache_similarity(answer: str) -> Optional[float]:
    match = re.search(r"相似度\s*(\d+)%", answer)
    return round(int(match.group(1)) / 100, 2) if match else None


def check_answer(item: Dict[str, Any], answer: str) -> List[str]:
    """返回未满足的断言；空列表表示通过。"""
    lower = answer.lower()
    missing: List[str] = []
    for text in item.get("expected_all", []):
        if text.lower() not in lower:
            missing.append(f"缺少: {text}")
    any_terms = item.get("expected_any", [])
    if any_terms and not any(term.lower() in lower for term in any_terms):
        missing.append("缺少任一: " + " / ".join(any_terms))
    for group in item.get("expected_groups", []):
        if not any(term.lower() in lower for term in group):
            missing.append("缺少任一: " + " / ".join(group))
    for pattern in item.get("forbidden_patterns", []):
        if re.search(pattern, answer):
            missing.append(f"命中禁止模式: {pattern}")
    return missing


def source_hit(item: Dict[str, Any], source_chunks: Sequence[Any]) -> Optional[bool]:
    if not item.get("expected_documents"):
        return None
    text = "\n".join(str(chunk) for chunk in source_chunks).lower()
    keywords = [str(k).lower() for k in item.get("expected_keywords", [])]
    return all(keyword in text for keyword in keywords) if keywords else None


def _query(client: httpx.Client, token: str, question: str, top_k: int) -> Dict[str, Any]:
    response = client.post(
        "/api/v1/rag/query",
        headers=_headers(token),
        json={"query": question, "top_k": top_k},
        timeout=TIMEOUT,
    )
    _check(
        response.status_code == 200,
        f"RAG 查询失败: HTTP {response.status_code} {response.text[:200]}",
    )
    return response.json()


# ----------------------------- 评测阶段 -----------------------------


def run_retrieval(
    client: httpx.Client,
    token: str,
    items: List[Dict[str, Any]],
    name_by_id: Dict[int, str],
    top_k: int,
) -> Dict[str, Any]:
    total = doc_hits = keyword_hits = 0
    reciprocal_rank = 0.0
    by_category: Dict[str, Dict[str, int]] = {}
    failures: List[Dict[str, Any]] = []

    for item in items:
        expected = item.get("expected_documents") or []
        if not expected:
            continue
        response = client.get(
            "/api/v1/rag/search",
            headers=_headers(token),
            params={"query": item["question"], "top_k": top_k},
            timeout=TIMEOUT,
        )
        _check(
            response.status_code == 200,
            f"检索失败 {item['id']}: HTTP {response.status_code} {response.text[:200]}",
        )
        results = response.json()["results"]
        retrieved_docs = [name_by_id.get(row["document_id"], "") for row in results]
        require_all = bool(item.get("require_all_documents"))
        if require_all:
            doc_hit = all(name in retrieved_docs for name in expected)
        else:
            doc_hit = any(name in retrieved_docs for name in expected)
        first_rank = next(
            (index + 1 for index, name in enumerate(retrieved_docs) if name in expected),
            None,
        )
        keywords = [str(k).lower() for k in item.get("expected_keywords", [])]
        expected_text = "\n".join(
            row["content"].lower()
            for row in results
            if name_by_id.get(row["document_id"]) in expected
        )
        keyword_hit = not keywords or all(keyword in expected_text for keyword in keywords)

        total += 1
        doc_hits += int(doc_hit)
        keyword_hits += int(keyword_hit)
        reciprocal_rank += (1.0 / first_rank) if first_rank else 0.0
        bucket = by_category.setdefault(item["category"], {"n": 0, "doc_hits": 0})
        bucket["n"] += 1
        bucket["doc_hits"] += int(doc_hit)

        if not (doc_hit and keyword_hit):
            failures.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "doc_hit": doc_hit,
                    "keyword_hit": keyword_hit,
                    "retrieved": retrieved_docs,
                }
            )
        print(
            f"[{'HIT ' if doc_hit and keyword_hit else 'MISS'}] retrieval {item['id']} "
            f"rank={first_rank or '-'} doc={int(doc_hit)} keyword={int(keyword_hit)}"
        )

    return {
        "n": total,
        "recall_at_k": _rate(doc_hits, total),
        "mrr": round(reciprocal_rank / total, 4) if total else 0.0,
        "keyword_hit_rate": _rate(keyword_hits, total),
        "by_category": {
            name: {"n": bucket["n"], "recall": _rate(bucket["doc_hits"], bucket["n"])}
            for name, bucket in sorted(by_category.items())
        },
        "failures": failures,
    }


def run_answers(
    client: httpx.Client,
    token: str,
    items: List[Dict[str, Any]],
    top_k: int,
    db: Session,
    user_id: int,
) -> Dict[str, Any]:
    total = passed = source_hits = source_checked = 0
    cache_hits = 0
    total_latency = 0.0
    by_category: Dict[str, Dict[str, int]] = {}
    failures: List[Dict[str, Any]] = []

    for item in items:
        # 每题清空缓存：答案层测的是“检索+生成”，不能被上一题写入的缓存污染
        invalidate_user_cache(db, user_id)
        db.commit()
        started = time.perf_counter()
        data = _query(client, token, item["question"], top_k)
        latency_ms = (time.perf_counter() - started) * 1000
        answer = data.get("answer") or ""
        chunks = data.get("source_chunks") or []
        hit = is_cache_hit(answer)
        missing = check_answer(item, answer)
        src = source_hit(item, chunks)

        total += 1
        total_latency += latency_ms
        passed += int(not missing)
        cache_hits += int(hit)
        if src is not None:
            source_checked += 1
            source_hits += int(src)
        bucket = by_category.setdefault(item["category"], {"n": 0, "passed": 0})
        bucket["n"] += 1
        bucket["passed"] += int(not missing)

        if missing:
            failures.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "missing": missing,
                    "cache_hit": hit,
                    "source_hit": src,
                    "answer": answer[:300],
                }
            )
        print(
            f"[{'PASS' if not missing else 'FAIL'}] answer {item['id']} "
            f"cache={int(hit)} source={src} latency={latency_ms:.0f}ms "
            f"missing={'; '.join(missing) if missing else '-'}"
        )

    return {
        "n": total,
        "pass_rate": _rate(passed, total),
        "source_hit_rate": _rate(source_hits, source_checked),
        "avg_latency_ms": round(total_latency / total) if total else 0,
        "unexpected_cache_hits": cache_hits,
        "by_category": {
            name: {"n": bucket["n"], "pass_rate": _rate(bucket["passed"], bucket["n"])}
            for name, bucket in sorted(by_category.items())
        },
        "failures": failures,
    }


def classify_negative_reject(
    similarity: float,
    cached_question: str,
    negative_question: str,
    *,
    has_sources: bool,
) -> str:
    """按 lookup_semantic_cache 的判定顺序归因单个候选的拒绝机制。

    below_candidate/guard 是确定性拒绝；llm_judge 是概率性拒绝；
    direct_hit_band 表示候选本应直通命中，未命中只能来自缓存外因素。
    数字/专名守卫只认 ASCII token，纯中文实体替换在直通带没有任何静态防线。
    """
    if similarity < settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD:
        return "below_candidate"
    if _numeric_tokens(cached_question) != _numeric_tokens(negative_question):
        return "guard"
    # RAG 评测走 require_sources=True：无来源快照的候选按未命中处理
    if not has_sources:
        return "guard"
    if similarity < settings.SEMANTIC_CACHE_THRESHOLD or (
        _entity_tokens(cached_question) != _entity_tokens(negative_question)
    ):
        return "llm_judge"
    return "direct_hit_band"


def _attribute_negative(
    db: Session,
    user_id: int,
    negative_question: str,
    negative_ok: bool,
    started_at: datetime,
) -> Dict[str, Any]:
    """负例查询后归因：相似度 + 拒绝机制 + 灰区校验的真实响应。

    向量直接读 DB：路由把同一条 query_vector 传给 lookup 和 store，
    负例条目里的向量就是判定时用的那条，无需重嵌（未落库时才回退重嵌）。
    """
    db.expire_all()
    entries = (
        db.query(QACacheEntry)
        .filter(
            QACacheEntry.user_id == user_id,
            QACacheEntry.embedding_model == settings.EMBEDDING_MODEL_NAME,
        )
        .all()
    )
    negative_entry = next((e for e in entries if e.question == negative_question), None)
    candidates = [e for e in entries if e.question != negative_question]

    vector = None
    if negative_entry is not None:
        vector = _parse_embedding(negative_entry.embedding)
    elif candidates:
        try:
            vector = asyncio.run(_embed_query(db, negative_question))
        except Exception as exc:
            print(f"[WARN] 负例向量重嵌失败，无法归因: {exc}")

    scored: List[tuple] = []
    if vector is not None:
        for entry in candidates:
            similarity = _cosine_similarity(vector, _parse_embedding(entry.embedding))
            scored.append(
                (
                    similarity,
                    classify_negative_reject(
                        similarity,
                        entry.question,
                        negative_question,
                        has_sources=bool(entry.source_chunks),
                    ),
                )
            )

    judge_responses = [
        log.response
        for log in db.query(LLMCallLog).filter(
            LLMCallLog.user_id == user_id,
            LLMCallLog.endpoint == "/semantic-cache/verify",
            LLMCallLog.prompt.contains(negative_question),
            # 评测账号的校验日志跨轮累积，只取本轮，否则历史响应混进证据
            LLMCallLog.created_at >= started_at,
        )
    ]

    reasons = [reason for _, reason in scored]
    if not negative_ok:
        reason = "hit"
    elif "llm_judge" in reasons:
        # 进了灰区却没有校验记录：judge 异常/缺 key 被静默按不命中，是故障不是安全
        reason = "llm_judge" if judge_responses else "other"
    elif "guard" in reasons:
        reason = "guard"
    elif reasons and all(r == "below_candidate" for r in reasons):
        reason = "below_candidate"
    else:
        reason = "other"

    return {
        # pgvector 读回 float32，round 不会转回 Python float，必须显式 cast 才能落 JSON
        "negative_similarity": round(float(max(s for s, _ in scored)), 4) if scored else None,
        "negative_reject_reason": reason,
        "negative_judge_responses": judge_responses,
    }


def run_cache(
    client: httpx.Client,
    token: str,
    pairs: List[Dict[str, Any]],
    db: Session,
    user_id: int,
    top_k: int,
    started_at: datetime,
) -> Dict[str, Any]:
    paraphrase_hits = negative_rejects = 0
    details: List[Dict[str, Any]] = []

    for pair in pairs:
        # 组间必须清缓存：上一组的 negative 会成为本组 base/negative 的命中源
        # （sick-leave 的 negative 与 annual-leave 的 base 几乎同句）
        invalidate_user_cache(db, user_id)
        db.commit()
        base = _query(client, token, pair["base"], top_k)
        paraphrase = _query(client, token, pair["paraphrase"], top_k)
        negative = _query(client, token, pair["negative"], top_k)

        paraphrase_ok = is_cache_hit(paraphrase["answer"])
        negative_ok = not is_cache_hit(negative["answer"])
        paraphrase_hits += int(paraphrase_ok)
        negative_rejects += int(negative_ok)
        attribution = _attribute_negative(db, user_id, pair["negative"], negative_ok, started_at)
        details.append(
            {
                "id": pair["id"],
                "base_cached_unexpectedly": is_cache_hit(base["answer"]),
                "paraphrase_hit": paraphrase_ok,
                "paraphrase_similarity": cache_similarity(paraphrase["answer"]),
                "negative_reject": negative_ok,
                **attribution,
            }
        )
        print(
            f"[{'OK  ' if paraphrase_ok and negative_ok else 'FAIL'}] cache {pair['id']} "
            f"paraphrase={int(paraphrase_ok)} negative_reject={int(negative_ok)} "
            f"sim={attribution['negative_similarity']} "
            f"reason={attribution['negative_reject_reason']}"
        )

    breakdown = {key: 0 for key in ("below_candidate", "guard", "llm_judge", "other", "hit")}
    for detail in details:
        breakdown[detail["negative_reject_reason"]] += 1
    return {
        "pairs": len(pairs),
        "paraphrase_hit_rate": _rate(paraphrase_hits, len(pairs)),
        "negative_reject_rate": _rate(negative_rejects, len(pairs)),
        "negative_reject_breakdown": breakdown,
        "details": details,
    }


def _stream_once(client: httpx.Client, token: str, question: str, top_k: int) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    last_data = ""
    with client.stream(
        "POST",
        "/api/v1/rag/query/stream",
        headers=_headers(token),
        json={"query": question, "top_k": top_k},
        timeout=TIMEOUT,
    ) as response:
        if response.status_code != 200:
            body = response.read().decode("utf-8", errors="replace")
            raise EvalFailure(f"流式查询失败: HTTP {response.status_code} {body[:200]}")
        for line in response.iter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            last_data = payload
            if payload == "[DONE]":
                continue
            events.append(json.loads(payload))

    text = "".join(str(event.get("content", "")) for event in events)
    errors = [event["error"] for event in events if "error" in event]
    return {
        "question": question,
        "done_last": last_data == "[DONE]",
        "has_source_event": any("source_chunks" in event for event in events),
        "cache_hit": is_cache_hit(text),
        "chars": len(text),
        "errors": errors,
    }


def run_stream(client: httpx.Client, token: str, top_k: int) -> Dict[str, Any]:
    checks = [
        _stream_once(client, token, "J103045 测试岗要求会用什么自动化测试工具？", top_k),
        _stream_once(client, token, "J106366 这个岗位要求掌握哪些编程语言？", top_k),
    ]
    passed = sum(
        1
        for check in checks
        if check["done_last"] and check["has_source_event"] and not check["errors"]
    )
    for check in checks:
        flag = "PASS" if check["done_last"] and check["has_source_event"] else "FAIL"
        print(
            f"[{flag}] stream done_last={int(check['done_last'])} "
            f"source_event={int(check['has_source_event'])} cache={int(check['cache_hit'])}"
        )
    return {"n": len(checks), "pass_rate": _rate(passed, len(checks)), "checks": checks}


# ----------------------------- 元信息与报告 -----------------------------


def collect_cost(db: Session, user_id: int, started_at: datetime) -> Dict[str, Any]:
    logs = (
        db.query(LLMCallLog)
        .filter(
            LLMCallLog.user_id == user_id,
            LLMCallLog.created_at >= started_at,
        )
        .all()
    )
    prompt_tokens = sum(log.prompt_tokens or 0 for log in logs)
    completion_tokens = sum(log.completion_tokens or 0 for log in logs)
    cost = 0.0
    for log in logs:
        cost += estimate_cost_cny(
            db, log.model_name, log.prompt_tokens or 0, log.completion_tokens or 0
        )
    return {
        "llm_calls": len(logs),
        "failed_calls": sum(1 for log in logs if log.status != "success"),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_cny": round(cost, 6),
    }


def _load_previous_report(out_root: Path, current: Path) -> Optional[Dict[str, Any]]:
    if not out_root.exists():
        return None
    for path in sorted(out_root.iterdir(), reverse=True):
        if path == current or not path.is_dir():
            continue
        report = path / "report.json"
        if report.exists():
            try:
                return json.loads(report.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
    return None


def _delta(current: float, previous: Optional[float]) -> str:
    if previous is None:
        return ""
    diff = current - previous
    return f" ({diff:+.2f})"


def render_markdown(report: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> str:
    run = report["run"]
    prev_stages = (previous or {}).get("stages", {})
    lines = [
        f"# 合成知识库评测报告 {run['id']}",
        "",
        f"- 结论：**{report['verdict']}**",
        f"- 时间：{run['started_at']} → {run['finished_at']}（{run['duration_s']}s）",
        f"- 代码版本：`{run['git_commit']}`",
        f"- LLM：`{run['llm_model']}`；Embedding：`{run['embedding_model']}`；top_k={run['top_k']}",
        f"- 语料：{run['corpus_documents']} 篇 / {run['corpus_chunks']} 个 chunk；"
        f"题集：{run['eval_questions']} 题；缓存对：{run['cache_pairs']} 组",
        f"- 成本：¥{report['cost']['cost_cny']:.4f}（{report['cost']['llm_calls']} 次调用，"
        f"{report['cost']['prompt_tokens']} + {report['cost']['completion_tokens']} tokens）",
        "",
        "## 指标",
        "",
        "| 阶段 | 指标 | 本轮 | 上一轮 |",
        "|---|---|---|---|",
    ]

    retrieval = report["stages"]["retrieval"]
    answer = report["stages"]["answer"]
    cache = report["stages"].get("cache")
    stream = report["stages"].get("stream")
    prev_retrieval = prev_stages.get("retrieval") or {}
    prev_answer = prev_stages.get("answer") or {}
    prev_cache = prev_stages.get("cache") or {}
    prev_stream = prev_stages.get("stream") or {}

    lines.append(
        f"| 检索 | recall@{run['top_k']} | {retrieval['recall_at_k']:.2f}"
        f"{_delta(retrieval['recall_at_k'], prev_retrieval.get('recall_at_k'))} "
        f"| {prev_retrieval.get('recall_at_k', '-')} |"
    )
    lines.append(
        f"| 检索 | MRR | {retrieval['mrr']:.3f}"
        f"{_delta(retrieval['mrr'], prev_retrieval.get('mrr'))} "
        f"| {prev_retrieval.get('mrr', '-')} |"
    )
    lines.append(
        f"| 检索 | keyword_hit | {retrieval['keyword_hit_rate']:.2f}"
        f"{_delta(retrieval['keyword_hit_rate'], prev_retrieval.get('keyword_hit_rate'))} "
        f"| {prev_retrieval.get('keyword_hit_rate', '-')} |"
    )
    lines.append(
        f"| 答案 | pass_rate | {answer['pass_rate']:.2f}"
        f"{_delta(answer['pass_rate'], prev_answer.get('pass_rate'))} "
        f"| {prev_answer.get('pass_rate', '-')} |"
    )
    lines.append(
        f"| 答案 | source_hit | {answer['source_hit_rate']:.2f}"
        f"{_delta(answer['source_hit_rate'], prev_answer.get('source_hit_rate'))} "
        f"| {prev_answer.get('source_hit_rate', '-')} |"
    )
    lines.append(
        f"| 答案 | 平均延迟 | {answer['avg_latency_ms']}ms | "
        f"{prev_answer.get('avg_latency_ms', '-')} |"
    )
    if cache:
        lines.append(
            f"| 缓存 | 改写命中 | {cache['paraphrase_hit_rate']:.2f}"
            f"{_delta(cache['paraphrase_hit_rate'], prev_cache.get('paraphrase_hit_rate'))} "
            f"| {prev_cache.get('paraphrase_hit_rate', '-')} |"
        )
        lines.append(
            f"| 缓存 | 负例拒绝 | {cache['negative_reject_rate']:.2f}"
            f"{_delta(cache['negative_reject_rate'], prev_cache.get('negative_reject_rate'))} "
            f"| {prev_cache.get('negative_reject_rate', '-')} |"
        )
    if stream:
        lines.append(
            f"| 流式 | 通过率 | {stream['pass_rate']:.2f}"
            f"{_delta(stream['pass_rate'], prev_stream.get('pass_rate'))} "
            f"| {prev_stream.get('pass_rate', '-')} |"
        )

    lines.extend(["", "## 分类表现", ""])
    lines.append("| 分类 | 检索 n / recall | 答案 n / pass |")
    lines.append("|---|---|---|")
    categories = sorted(set(retrieval["by_category"]) | set(answer["by_category"]))
    for category in categories:
        r = retrieval["by_category"].get(category)
        a = answer["by_category"].get(category)
        retrieval_cell = f"{r['n']} / {r['recall']:.2f}" if r else "-"
        answer_cell = f"{a['n']} / {a['pass_rate']:.2f}" if a else "-"
        lines.append(f"| {category} | {retrieval_cell} | {answer_cell} |")

    failures = [("检索", row) for row in retrieval["failures"]]
    failures += [("答案", row) for row in answer["failures"]]
    if failures:
        lines.extend(["", "## 失败明细", ""])
        for stage, row in failures:
            if stage == "检索":
                lines.append(
                    f"- [{stage}] `{row['id']}` ({row['category']}) "
                    f"doc={row['doc_hit']} keyword={row['keyword_hit']} "
                    f"retrieved={row['retrieved']}"
                )
            else:
                lines.append(
                    f"- [{stage}] `{row['id']}` ({row['category']}) "
                    f"missing={'、'.join(row['missing'])}；回答：{row['answer'][:160]}"
                )

    if cache:
        breakdown = cache["negative_reject_breakdown"]
        lines.extend(
            [
                "",
                "## 缓存负例归因",
                "",
                f"确定性拒绝：below_candidate {breakdown['below_candidate']} + "
                f"guard {breakdown['guard']}；概率性拒绝：llm_judge {breakdown['llm_judge']}；"
                f"other {breakdown['other']}；误命中 {breakdown['hit']}",
                "",
                "| 组 | 负例相似度 | 拒绝机制 | 灰区校验响应 |",
                "|---|---|---|---|",
            ]
        )
        for detail in cache["details"]:
            similarity = detail["negative_similarity"]
            responses = "/".join(str(r) for r in detail["negative_judge_responses"]) or "-"
            lines.append(
                f"| {detail['id']} | {similarity if similarity is not None else '-'} "
                f"| {detail['negative_reject_reason']} | {responses} |"
            )

    if cache and any(not d["negative_reject"] for d in cache["details"]):
        lines.extend(["", "## 缓存误命中", ""])
        for detail in cache["details"]:
            if not detail["negative_reject"]:
                lines.append(f"- `{detail['id']}` 负例命中了缓存")

    if cache and any(not d["paraphrase_hit"] for d in cache["details"]):
        lines.extend(["", "## 缓存改写未命中", ""])
        for detail in cache["details"]:
            if not detail["paraphrase_hit"]:
                similarity = detail.get("paraphrase_similarity")
                lines.append(
                    f"- `{detail['id']}` 同义改写未命中缓存"
                    f"（相似度 {similarity if similarity is not None else '未进入直通阈值'}）"
                )

    if answer["unexpected_cache_hits"]:
        lines.append(
            f"\n> 注意：答案层有 {answer['unexpected_cache_hits']} 题命中缓存，"
            "说明题集之间存在语义重叠，该轮答案指标需谨慎解读。"
        )

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 语料与题集固定，分数用于跨轮回归比较；换语料后不与历史报告直接可比。",
            "- 合成题只能证明检索/缓存链路是否退化，不能代表真实用户场景的质量。",
            "- 报告仅在 `git_commit`、模型和 `top_k` 一致时横向比较有意义。",
            "- 负例归因：below_candidate（相似度未达候选下限）与 guard（数字/来源守卫）是确定性拒绝；"
            "llm_judge 是概率性拒绝，随模型与措辞波动；other 表示缓存外因素"
            "（校验故障、问句不可缓存等），需排查。",
            "",
        ]
    )
    return "\n".join(lines)


# ----------------------------- 主流程 -----------------------------


def run(args: argparse.Namespace) -> int:
    if settings.LLM_MOCK and not args.allow_mock:
        raise SystemExit("LLM_MOCK=true，评测会失去意义；确需联调请加 --allow-mock")

    corpus_dir = Path(args.corpus_dir)
    items = _load_jsonl(Path(args.eval_set))
    pairs = [] if args.skip_cache else _load_jsonl(Path(args.cache_pairs))
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == EMAIL).first()
        if user is None:
            with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
                login_or_register(client)
            user = db.query(User).filter(User.email == EMAIL).first()
        _check(user is not None, "评测账号创建后仍未找到用户记录")
        llm_model = get_llm_client(user).model_name

        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            token = login_or_register(client)
            removed = clear_documents(client, token)
            invalidate_user_cache(db, user.id)
            db.commit()
            print(f"== eval {run_id} account={EMAIL} cleared_docs={removed}")

            uploaded = upload_corpus(client, token, corpus_dir)
            doc_ids = [doc["id"] for doc in uploaded]
            ready = wait_ready(client, token, doc_ids, args.timeout)
            name_by_id = {doc["id"]: doc["filename"] for doc in uploaded}
            print(f"[PASS] ingest {len(ready)}/{len(uploaded)} ready")

            retrieval = run_retrieval(client, token, items, name_by_id, args.top_k)
            answer = run_answers(client, token, items, args.top_k, db, user.id)
            cache = (
                run_cache(client, token, pairs, db, user.id, args.top_k, started_at)
                if pairs
                else None
            )
            stream = None if args.skip_stream else run_stream(client, token, args.top_k)

            if args.cleanup:
                clear_documents(client, token)
                invalidate_user_cache(db, user.id)
                db.commit()

        finished_at = datetime.now(timezone.utc)
        cost = collect_cost(db, user.id, started_at)
    finally:
        db.close()

    stages = {"retrieval": retrieval, "answer": answer, "cache": cache, "stream": stream}
    # 改写未命中不算硬失败（灰区可能被 LLM 校验拒绝），误命中/负例漏拒才算
    failed = bool(retrieval["failures"] or answer["failures"])
    if cache:
        failed = failed or cache["negative_reject_rate"] < 1.0
    if stream:
        failed = failed or stream["pass_rate"] < 1.0
    verdict = "fail" if failed else "pass"

    report = {
        "run": {
            "id": run_id,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_s": round(time.perf_counter() - started_perf, 1),
            "base_url": BASE_URL,
            "git_commit": GIT_COMMIT,
            "llm_model": llm_model,
            "embedding_model": settings.EMBEDDING_MODEL_NAME,
            "top_k": args.top_k,
            "corpus_documents": len(uploaded),
            "corpus_chunks": sum(
                (ready.get(doc["id"], {}).get("chunks_count") or 0) for doc in uploaded
            ),
            "eval_questions": len(items),
            "cache_pairs": len(pairs),
            "corpus": [
                {
                    "document_id": doc["id"],
                    "filename": doc["filename"],
                    "chunks": ready.get(doc["id"], {}).get("chunks_count"),
                }
                for doc in uploaded
            ],
        },
        "stages": stages,
        "cost": cost,
        "verdict": verdict,
    }

    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    previous = _load_previous_report(RUNS_DIR, out_dir)
    (out_dir / "report.md").write_text(render_markdown(report, previous), encoding="utf-8")

    print(
        "\nSUMMARY "
        + json.dumps(
            {
                "verdict": verdict,
                "retrieval": {
                    key: retrieval[key] for key in ("n", "recall_at_k", "mrr", "keyword_hit_rate")
                },
                "answer": {
                    key: answer[key]
                    for key in ("n", "pass_rate", "source_hit_rate", "avg_latency_ms")
                },
                "cache": cache
                and {
                    key: cache[key]
                    for key in (
                        "pairs",
                        "paraphrase_hit_rate",
                        "negative_reject_rate",
                        "negative_reject_breakdown",
                    )
                },
                "stream": stream and {"n": stream["n"], "pass_rate": stream["pass_rate"]},
                "cost_cny": cost["cost_cny"],
            },
            ensure_ascii=False,
        )
    )
    print(f"REPORT {out_dir}/report.md")

    return 1 if (args.strict and failed) else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic knowledge-base evaluation pipeline")
    parser.add_argument("--corpus-dir", default="evaluation/synth/corpus")
    parser.add_argument("--eval-set", default="evaluation/synth/eval_set.jsonl")
    parser.add_argument("--cache-pairs", default="evaluation/synth/cache_pairs.jsonl")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("EVAL_TIMEOUT", "300")))
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument("--skip-stream", action="store_true")
    parser.add_argument("--cleanup", action="store_true", help="跑完删除评测文档与缓存")
    parser.add_argument("--strict", action="store_true", help="存在失败项时返回非 0")
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
