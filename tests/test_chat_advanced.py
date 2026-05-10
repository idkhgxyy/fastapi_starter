import pytest
import json
from unittest.mock import patch, AsyncMock
from app.services.llm_service import generate_chat_reply_stream

def test_chat_rate_limiting(client):
    # 1. Create a user
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

    # 2. Mock LLM service
    with patch("app.api.routers.chat.generate_chat_reply", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Mocked Reply"
        
        status_codes = []
        for _ in range(25):
            response = client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "hello", "stream": False}
            )
            status_codes.append(response.status_code)
            
        assert 429 in status_codes
        assert status_codes.count(200) <= 20
        assert status_codes.count(429) >= 5

def test_chat_sse_stream(client):
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

    async def mock_stream_generator(*args, **kwargs):
        yield 'data: {"content": "Hello"}\n\n'
        yield 'data: [DONE]\n\n'

    with patch("app.api.routers.chat.generate_chat_reply_stream", mock_stream_generator):
        with client.stream("POST", "/api/chat/", headers=headers, json={"message": "hello", "stream": True}) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            content = response.read().decode("utf-8")
            assert 'data: {"content": "Hello"}' in content
            assert 'data: [DONE]' in content
