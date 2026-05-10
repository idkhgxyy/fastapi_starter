import pytest
import json
from unittest.mock import patch, AsyncMock
from app.services.llm_service import generate_chat_reply_stream

def test_chat_rate_limiting(client):
    # 1. 创建用户并获取 token
    client.post(
        "/api/users/",
        json={
            "username": "ratelimit_user",
            "email": "ratelimit@example.com",
            "password": "password123"
        },
    )
    login_resp = client.post(
        "/api/auth/login",
        data={
            "username": "ratelimit@example.com",
            "password": "password123"
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 模拟 LLM 服务以避免真实的 LLM 调用消耗时间和费用
    with patch("app.api.routers.chat.generate_chat_reply", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Mocked Reply"
        
        status_codes = []
        # 发送 25 次请求，由于限流是 20次/60秒，应该会有 429
        for _ in range(25):
            response = client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "你好", "stream": False}
            )
            status_codes.append(response.status_code)
            
        assert 429 in status_codes
        # 前 20 次应该是 200，后面的是 429
        assert status_codes.count(200) <= 20
        assert status_codes.count(429) >= 5

def test_chat_sse_stream(client):
    # 测试 SSE 接口的 Header 和流式格式
    # 为避免受上一个限流测试的影响，使用另一个新用户
    client.post(
        "/api/users/",
        json={
            "username": "sse_user",
            "email": "sse@example.com",
            "password": "password123"
        },
    )
    login_resp = client.post(
        "/api/auth/login",
        data={
            "username": "sse@example.com",
            "password": "password123"
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 因为 TestClient 的 with 方式对 streaming 支持有限，可以尝试 mock 底层 generator
    async def mock_stream_generator(*args, **kwargs):
        yield 'data: {"content": "Hello"}\n\n'
        yield 'data: [DONE]\n\n'

    with patch("app.api.routers.chat.generate_chat_reply_stream", mock_stream_generator):
        with client.stream("POST", "/api/chat/", headers=headers, json={"message": "你好", "stream": True}) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            # 读取内容
            content = response.read().decode("utf-8")
            assert 'data: {"content": "Hello"}' in content
            assert 'data: [DONE]' in content
