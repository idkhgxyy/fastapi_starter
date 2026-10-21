"""会话持久化与隔离测试。"""

from types import SimpleNamespace

import pytest

from app.models.conversation import ConversationMessage
from app.services import llm_service


def _create_user_and_login(client, suffix: str) -> tuple[str, int]:
    email = f"conv-{suffix}@example.com"
    password = "password123"
    client.post(
        "/api/v1/users/",
        json={"username": f"convuser-{suffix}", "email": email, "password": password},
    )
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    user_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()[
        "id"
    ]
    return token, user_id


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class FakeStream:
    def __init__(self, reply: str):
        self._chunks = [
            SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(delta=SimpleNamespace(content=reply, reasoning_content=None))
                ],
            ),
            SimpleNamespace(
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                choices=[],
            ),
        ]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)

    async def close(self):
        return None


@pytest.fixture
def fake_llm(monkeypatch):
    """记录每次发给模型的 messages，并按固定内容流式返回。"""
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return FakeStream("好的，这是回答。")

    info = SimpleNamespace(
        model_name="fake-model",
        client=SimpleNamespace(
            api_key="fake-key",
            chat=SimpleNamespace(completions=FakeCompletions()),
        ),
    )
    monkeypatch.setattr(llm_service, "get_llm_client", lambda user=None: info)
    monkeypatch.setattr(llm_service, "_build_fallback_info", lambda: None)
    # 缓存写入会触发 embedding，测试里统一短路
    monkeypatch.setattr(llm_service, "store_semantic_cache", lambda *a, **kw: _noop())
    return calls


async def _noop():
    return None


@pytest.fixture
def cache_misses(monkeypatch):
    calls = {"n": 0}

    async def fake_lookup(db, user_id, question):
        calls["n"] += 1
        return None

    monkeypatch.setattr(llm_service, "lookup_semantic_cache", fake_lookup)
    return calls


def _chat(client, token, message, conversation_id=None):
    payload = {"message": message, "stream": True}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = client.post("/api/v1/chat/", headers=_headers(token), json=payload)
    assert response.status_code == 200
    return response


class TestConversationCrud:
    def test_create_list_get_delete(self, client):
        token, _ = _create_user_and_login(client, "crud")

        created = client.post("/api/v1/conversations/", headers=_headers(token), json={})
        assert created.status_code == 201
        conversation_id = created.json()["id"]
        assert created.json()["title"] == "新对话"

        listed = client.get("/api/v1/conversations/", headers=_headers(token)).json()
        assert [c["id"] for c in listed] == [conversation_id]
        assert listed[0]["message_count"] == 0

        detail = client.get(f"/api/v1/conversations/{conversation_id}", headers=_headers(token))
        assert detail.status_code == 200
        assert detail.json()["messages"] == []

        deleted = client.delete(f"/api/v1/conversations/{conversation_id}", headers=_headers(token))
        assert deleted.status_code == 200
        assert (
            client.get(
                f"/api/v1/conversations/{conversation_id}", headers=_headers(token)
            ).status_code
            == 404
        )

    def test_isolation_between_users(self, client):
        token_a, _ = _create_user_and_login(client, "iso-a")
        token_b, _ = _create_user_and_login(client, "iso-b")

        conversation_id = client.post(
            "/api/v1/conversations/", headers=_headers(token_a), json={}
        ).json()["id"]

        assert (
            client.get(
                f"/api/v1/conversations/{conversation_id}", headers=_headers(token_b)
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/v1/conversations/{conversation_id}", headers=_headers(token_b)
            ).status_code
            == 404
        )
        assert client.get("/api/v1/conversations/", headers=_headers(token_b)).json() == []


class TestChatPersistence:
    def test_first_turn_persists_messages_and_title(self, client, fake_llm, cache_misses):
        token, _ = _create_user_and_login(client, "persist")
        conversation_id = client.post(
            "/api/v1/conversations/", headers=_headers(token), json={}
        ).json()["id"]

        _chat(client, token, "我的雅思备考计划怎么安排？", conversation_id)

        detail = client.get(
            f"/api/v1/conversations/{conversation_id}", headers=_headers(token)
        ).json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][0]["content"] == "我的雅思备考计划怎么安排？"
        assert detail["messages"][1]["content"] == "好的，这是回答。"
        # 标题自动取首条消息
        assert detail["title"] == "我的雅思备考计划怎么安排？"

    def test_second_turn_includes_history(self, client, fake_llm, cache_misses):
        token, _ = _create_user_and_login(client, "history")
        conversation_id = client.post(
            "/api/v1/conversations/", headers=_headers(token), json={}
        ).json()["id"]

        _chat(client, token, "第一轮问题", conversation_id)
        _chat(client, token, "第二轮问题", conversation_id)

        second_call_messages = fake_llm[-1]["messages"]
        roles = [m["role"] for m in second_call_messages]
        assert roles[0] == "system"
        assert {"role": "user", "content": "第一轮问题"} in second_call_messages
        assert {"role": "assistant", "content": "好的，这是回答。"} in second_call_messages

        detail = client.get(
            f"/api/v1/conversations/{conversation_id}", headers=_headers(token)
        ).json()
        assert len(detail["messages"]) == 4

    def test_second_turn_deleted_with_conversation(
        self, client, db_session, fake_llm, cache_misses
    ):
        token, _ = _create_user_and_login(client, "cascade")
        conversation_id = client.post(
            "/api/v1/conversations/", headers=_headers(token), json={}
        ).json()["id"]
        _chat(client, token, "会被级联删除的消息", conversation_id)

        assert (
            db_session.query(ConversationMessage).filter_by(conversation_id=conversation_id).count()
            == 2
        )
        client.delete(f"/api/v1/conversations/{conversation_id}", headers=_headers(token))
        assert (
            db_session.query(ConversationMessage).filter_by(conversation_id=conversation_id).count()
            == 0
        )


class TestCacheScope:
    def test_lookup_skipped_when_conversation_has_history(self, client, fake_llm, cache_misses):
        token, _ = _create_user_and_login(client, "cache-scope")
        conversation_id = client.post(
            "/api/v1/conversations/", headers=_headers(token), json={}
        ).json()["id"]

        _chat(client, token, "第一轮", conversation_id)
        assert cache_misses["n"] == 1

        _chat(client, token, "第二轮", conversation_id)
        # 有历史时不查语义缓存，避免跨上下文误命中
        assert cache_misses["n"] == 1

    def test_cache_hit_still_persists_exchange(self, client, monkeypatch, fake_llm):
        token, _ = _create_user_and_login(client, "cache-hit")
        conversation_id = client.post(
            "/api/v1/conversations/", headers=_headers(token), json={}
        ).json()["id"]

        class FakeEntry:
            answer = "缓存里的历史回答"
            original_cost_cny = 0.001

        async def fake_lookup(db, user_id, question):
            return FakeEntry(), 0.99

        monkeypatch.setattr(llm_service, "lookup_semantic_cache", fake_lookup)

        response = _chat(client, token, "命中缓存的问题", conversation_id)
        assert "缓存命中" in response.text

        detail = client.get(
            f"/api/v1/conversations/{conversation_id}", headers=_headers(token)
        ).json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][1]["content"] == "缓存里的历史回答"
        assert fake_llm == []
