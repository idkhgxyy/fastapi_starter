import json
import time

import httpx


BASE_URL = "http://localhost:8000/api"
TEST_USER = {
    "username": "admin",
    "email": "admin@example.com",
    "password": "password123",
    "full_name": "Test Admin",
}

QUESTION_SET = [
    {"name": "普通对话", "message": "请用一句话介绍你自己。"},
    {"name": "工具调用-天气", "message": "帮我查一下北京今天天气。"},
    {"name": "工具调用-任务", "message": "帮我创建一个任务，标题是明天复习 RAG，描述是看向量检索和重排。"},
]


def ensure_login(client: httpx.Client) -> str:
    client.post("/users/", json=TEST_USER)
    response = client.post(
        "/auth/login",
        data={"username": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=180.0) as client:
        token = ensure_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        results = []
        for item in QUESTION_SET:
            started_at = time.perf_counter()
            response = client.post("/chat/", json={"message": item["message"]}, headers=headers)
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            payload = response.json()
            results.append(
                {
                    "name": item["name"],
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "reply": payload.get("reply"),
                }
            )

        stats_response = client.get("/observability/llm-stats?days=7", headers=headers)
        stats_response.raise_for_status()

    print("=== 离线评测结果 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("\n=== 近 7 天 LLM 统计 ===")
    print(json.dumps(stats_response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
