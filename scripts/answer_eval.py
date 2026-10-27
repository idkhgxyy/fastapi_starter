"""RAG 答案质量评测。

直接调用 RAGService 和真实 LLM，检查回答是否包含预期事实；不经过 HTTP/缓存，
HTTP、登录、缓存和流式由 smoke_test/ui_smoke_test 覆盖。评测不写 llm_call_logs，
避免污染线上观测数据。

在 api 容器内运行：
    python scripts/answer_eval.py
    python scripts/answer_eval.py --limit 5
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.services.llm_observability_service import extract_usage
from app.services.llm_service import get_llm_client
from app.services.pricing_service import estimate_cost_cny
from app.services.rag_service import RAGService


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _resolve_expected_ids(
    db, user_id: int, filenames: Sequence[str]
) -> tuple[set[int], set[str]]:
    docs = (
        db.query(Document)
        .filter(Document.owner_id == user_id, Document.filename.in_(filenames))
        .all()
    )
    found = {doc.filename for doc in docs}
    return {doc.id for doc in docs}, set(filenames) - found


def _check_facts(item: Dict[str, Any], answer: str) -> List[str]:
    """返回未满足的事实描述；空列表表示通过。"""
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
    return missing


async def _evaluate(db, items: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
    service = RAGService(db)
    total = source_hits = answer_hits = 0
    total_cost = 0.0
    total_latency_ms = 0.0
    skipped = 0
    failures: List[str] = []

    for item in items:
        user = db.query(User).filter(User.email == item["user"]).first()
        if user is None:
            print(f"[SKIP] {item['id']}: user not found: {item['user']}")
            skipped += 1
            continue

        expected_ids, missing_docs = _resolve_expected_ids(
            db, user.id, item["expected_documents"]
        )
        if missing_docs:
            print(f"[SKIP] {item['id']}: documents not found: {sorted(missing_docs)}")
            skipped += 1
            continue

        started = time.perf_counter()
        knowledge = await service.build_knowledge_context(
            query=item["question"], owner_id=user.id, top_k=top_k
        )
        source_ids = {chunk.document_id for chunk in knowledge.chunks}
        source_ids.update(doc.id for doc in knowledge.summary_documents)
        source_hit = bool(source_ids & expected_ids)
        source_hits += int(source_hit)

        if not knowledge.context:
            answer = ""
        else:
            info = get_llm_client(user)
            system_prompt = (
                "你是一个专业的问答助手。请基于以下提供的参考资料，准确回答用户的问题。\n"
                "如果你不知道答案，或者参考资料中没有相关信息，请直接说明，不要编造。\n\n"
                f"{knowledge.context}"
            )
            response = await info.client.chat.completions.create(
                model=info.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": item["question"]},
                ],
                temperature=0.1,
            )
            answer = (response.choices[0].message.content or "").strip()
            prompt_tokens, completion_tokens, _ = extract_usage(response)
            total_cost += estimate_cost_cny(
                db, info.model_name, prompt_tokens, completion_tokens
            )

        latency_ms = (time.perf_counter() - started) * 1000
        missing = _check_facts(item, answer)
        answer_hit = not missing
        total += 1
        answer_hits += int(answer_hit)
        total_latency_ms += latency_ms
        if not answer_hit:
            failures.append(item["id"])

        print(
            f"[{'PASS' if answer_hit else 'FAIL'}] {item['id']} "
            f"source={int(source_hit)} latency={latency_ms:.0f}ms "
            f"missing={'; '.join(missing) if missing else '-'}"
        )

    summary = {
        "questions": total,
        "skipped": skipped,
        "source_hit_rate": round(source_hits / total, 4) if total else 0.0,
        "answer_hit_rate": round(answer_hits / total, 4) if total else 0.0,
        "avg_latency_ms": round(total_latency_ms / total) if total else 0,
        "total_cost_cny": round(total_cost, 6),
        "failed": failures,
    }
    print(
        f"answer_eval: n={total} source_hit={summary['source_hit_rate']:.2f} "
        f"answer_hit={summary['answer_hit_rate']:.2f} "
        f"avg_latency={summary['avg_latency_ms']}ms "
        f"cost=¥{summary['total_cost_cny']:.4f}"
    )
    return summary


async def _run(args: argparse.Namespace) -> None:
    dataset = Path(args.dataset)
    if not dataset.exists():
        raise SystemExit(f"dataset not found: {dataset}")
    items = _load_jsonl(dataset)
    if args.limit:
        items = items[: args.limit]

    db = SessionLocal()
    try:
        summary = await _evaluate(db, items, args.top_k)
    finally:
        db.close()
    print("\nSUMMARY " + json.dumps(summary, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG answer-quality evaluation")
    parser.add_argument("--dataset", default="evaluation/answer_eval_set.jsonl")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
