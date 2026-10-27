"""部署后真实 HTTP 冒烟测试。

在 api 容器内执行（默认请求 127.0.0.1:8000）：

    python scripts/smoke_test.py
    # 或本地：make smoke

覆盖：健康检查、登录/自动注册、上传到 ready、真实 RAG 回答、语义缓存命中、
换数字缓存拒绝、流式来源与 [DONE] 收尾、清理临时文档。失败返回非 0。
专用验收账号只访问自己的数据；账号已存在时直接登录。SMOKE_PASSWORD 必须由
环境变量或本地 .env 提供，脚本不内置默认密码。
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

BASE_URL = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.getenv("SMOKE_EMAIL", "smoke@example.com")
USERNAME = os.getenv("SMOKE_USERNAME", "smoke-tester")
TIMEOUT = float(os.getenv("SMOKE_TIMEOUT", "180"))


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


PASSWORD = os.getenv("SMOKE_PASSWORD") or _env_value("SMOKE_PASSWORD")
if not PASSWORD:
    raise SystemExit(
        "SMOKE_PASSWORD 未设置：请在环境变量或本地 .env 中配置（不要写进仓库）"
    )


class SmokeFailure(RuntimeError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_or_register(client: httpx.Client) -> str:
    login = client.post(
        "/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )
    if login.status_code == 200:
        return login.json()["access_token"]
    if login.status_code != 401:
        raise SmokeFailure(f"登录失败: HTTP {login.status_code} {login.text[:200]}")

    created = client.post(
        "/api/v1/users/",
        json={
            "username": USERNAME,
            "email": EMAIL,
            "password": PASSWORD,
            "full_name": "Smoke Tester",
        },
    )
    if created.status_code not in (200, 201):
        raise SmokeFailure(
            "验收账号不存在且注册失败: "
            f"HTTP {created.status_code} {created.text[:200]}（检查 SMOKE_EMAIL/PASSWORD）"
        )
    login = client.post(
        "/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )
    _check(login.status_code == 200, f"注册后登录失败: HTTP {login.status_code}")
    return login.json()["access_token"]


def _upload(client: httpx.Client, token: str, run_id: str) -> Tuple[int, str]:
    code = f"SMOKE-{run_id.upper()}"
    content = (
        f"# Smoke Test {run_id}\n\n"
        f"部署验收码：{code}\n\n"
        "这份文件只用于部署后的真实链路冒烟测试，验证上传、切块、向量化、"
        "检索、语义缓存和流式回答。\n"
    )
    response = client.post(
        "/api/v1/rag/upload",
        headers=_headers(token),
        files={"file": (f"smoke-{run_id}.md", content.encode("utf-8"), "text/markdown")},
    )
    _check(response.status_code == 202, f"上传失败: HTTP {response.status_code} {response.text[:200]}")
    return response.json()["id"], code


def _wait_ready(client: httpx.Client, token: str, document_id: int) -> None:
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        status = client.get(f"/api/v1/rag/documents/{document_id}", headers=_headers(token))
        _check(status.status_code == 200, f"查询文档状态失败: HTTP {status.status_code}")
        data = status.json()
        if data["status"] == "ready":
            _check(data["chunks_count"] > 0, "文档 ready 但 chunks_count=0")
            return
        if data["status"] == "failed":
            raise SmokeFailure(f"文档处理失败: {data.get('error_message')}")
        time.sleep(2)
    raise SmokeFailure(f"文档处理超时（{TIMEOUT:.0f}s）")


def _query(client: httpx.Client, token: str, question: str) -> Dict[str, Any]:
    response = client.post(
        "/api/v1/rag/query",
        headers=_headers(token),
        json={"query": question, "top_k": 3},
        timeout=TIMEOUT,
    )
    _check(response.status_code == 200, f"RAG 查询失败: HTTP {response.status_code} {response.text[:200]}")
    return response.json()


def _stream(client: httpx.Client, token: str, question: str) -> Tuple[List[Dict[str, Any]], str]:
    events: List[Dict[str, Any]] = []
    last_data = ""
    with client.stream(
        "POST",
        "/api/v1/rag/query/stream",
        headers=_headers(token),
        json={"query": question, "top_k": 3},
        timeout=TIMEOUT,
    ) as response:
        if response.status_code != 200:
            body = response.read().decode("utf-8", errors="replace")
            raise SmokeFailure(f"流式查询失败: HTTP {response.status_code} {body[:200]}")
        for line in response.iter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            last_data = payload
            if payload == "[DONE]":
                continue
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError as exc:
                raise SmokeFailure(f"非法 SSE 负载: {payload[:200]}") from exc
    return events, last_data


def _cleanup(client: httpx.Client, token: str, document_id: int) -> None:
    response = client.delete(
        f"/api/v1/rag/documents/{document_id}", headers=_headers(token)
    )
    if response.status_code == 200:
        print(f"[CLEAN] 已删除临时文档 id={document_id}")
    else:
        print(
            f"[WARN] 清理临时文档失败: HTTP {response.status_code} "
            f"{response.text[:200]}",
            file=sys.stderr,
        )


def main() -> int:
    run_id = uuid.uuid4().hex[:8]
    token = ""
    document_id = None
    print(f"== smoke test {BASE_URL} account={EMAIL} run={run_id}")

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        try:
            health = client.get("/api/v1/health/")
            _check(health.status_code == 200, f"健康检查失败: HTTP {health.status_code}")
            print("[PASS] 1/7 健康检查")

            token = _login_or_register(client)
            document_id, code = _upload(client, token, run_id)
            _wait_ready(client, token, document_id)
            print(f"[PASS] 2/7 登录 + 上传 ready（document_id={document_id}）")

            first = _query(client, token, "部署验收码是什么？")
            _check(code in first.get("answer", ""), "回答里没有验收码")
            _check(bool(first.get("source_chunks")), "回答没有来源片段")
            print("[PASS] 3/7 真实 RAG 回答 + 来源")

            paraphrase = _query(client, token, "这次部署的验收码是多少？")
            _check("缓存命中" in paraphrase.get("answer", ""), "同义改写没有命中缓存")
            _check(code in paraphrase.get("answer", ""), "缓存回答里没有验收码")
            _check(bool(paraphrase.get("source_chunks")), "缓存命中没有返回来源")
            print("[PASS] 4/7 同义改写缓存命中 + 来源")

            negative = _query(
                client, token, f"部署验收码是 NOT-9{run_id.upper()} 吗？"
            )
            _check("缓存命中" not in negative.get("answer", ""), "换数字仍命中缓存")
            print("[PASS] 5/7 换数字缓存未命中")

            events, last_data = _stream(client, token, "部署验收码是什么？")
            _check(last_data == "[DONE]", f"流式最后一条不是 [DONE]: {last_data[:80]}")
            stream_text = "".join(str(event.get("content", "")) for event in events)
            _check(code in stream_text, "流式回答里没有验收码")
            _check(
                any(event.get("source_chunks") for event in events),
                "流式回答没有来源事件",
            )
            print("[PASS] 6/7 流式命中 + 来源 + [DONE] 收尾")

            fresh = _stream(
                client,
                token,
                f"请复述部署验收码，并在回答里带上编号 9{run_id.upper()}。",
            )
            _check(fresh[1] == "[DONE]", f"真实流式最后一条不是 [DONE]: {fresh[1][:80]}")
            fresh_text = "".join(str(event.get("content", "")) for event in fresh[0])
            _check(code in fresh_text, "真实流式回答里没有验收码")
            _check(
                any(event.get("source_chunks") for event in fresh[0]),
                "真实流式回答没有来源事件",
            )
            print("[PASS] 7/7 真实 LLM 流式 + 来源 + [DONE] 收尾")

            return 0
        except Exception as exc:
            print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            if token and document_id is not None:
                _cleanup(client, token, document_id)


if __name__ == "__main__":
    sys.exit(main())
