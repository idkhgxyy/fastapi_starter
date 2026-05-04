from types import SimpleNamespace

from app.models.document import DOCUMENT_STATUS_QUEUED, DOCUMENT_STATUS_READY, Document
from app.services.rag_service import RAGService


def _create_user_and_login(client, suffix: str) -> str:
    email = f"rag-{suffix}@example.com"
    password = "password123"
    client.post(
        "/api/users/",
        json={
            "username": f"raguser-{suffix}",
            "email": email,
            "password": password,
        },
    )
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_upload_document_creates_async_job(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "upload")

    class DummyTask:
        id = "task-rag-upload-1"

    monkeypatch.setattr(
        "app.api.routers.rag.process_document_task.delay",
        lambda document_id: DummyTask(),
    )

    response = client.post(
        "/api/rag/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", b"hello rag", "text/plain")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == DOCUMENT_STATUS_QUEUED
    assert payload["processing_task_id"] == "task-rag-upload-1"
    assert payload["chunks_count"] == 0

    document = db_session.get(Document, payload["id"])
    assert document is not None
    assert document.status == DOCUMENT_STATUS_QUEUED
    assert document.processing_task_id == "task-rag-upload-1"
    assert document.owner_id is not None


def test_query_knowledge_base_uses_current_user_scope(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "query")
    user_id = int(client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"])

    ready_doc = Document(
        owner_id=user_id,
        filename="ready.txt",
        content="rag content",
        status=DOCUMENT_STATUS_READY,
        chunks_count=1,
    )
    db_session.add(ready_doc)
    db_session.commit()

    async def fake_retrieve(_self, *, query=None, owner_id, top_k=None):
        assert owner_id == user_id
        assert query == "我的知识库里有什么？"
        assert top_k == 2
        return [SimpleNamespace(content="只属于当前用户的知识片段")]

    def fake_get_llm_client():
        class DummyClient:
            class chat:
                class completions:
                    @staticmethod
                    async def create(**_kwargs):
                        return SimpleNamespace(
                            choices=[SimpleNamespace(message=SimpleNamespace(content="基于当前用户文档的回答"))],
                            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=7, total_tokens=12),
                        )

        return DummyClient()

    monkeypatch.setattr(RAGService, "retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr("app.api.routers.rag.get_llm_client", fake_get_llm_client)

    response = client.post(
        "/api/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "我的知识库里有什么？", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "基于当前用户文档的回答"
    assert payload["source_chunks"] == ["只属于当前用户的知识片段"]
