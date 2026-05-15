from types import SimpleNamespace

from app.models.document import DOCUMENT_STATUS_QUEUED, DOCUMENT_STATUS_READY, Document
from app.services.rag_service import RAGService


def _create_user_and_login(client, suffix: str) -> str:
    email = f"rag-{suffix}@example.com"
    password = "password123"
    client.post(
        "/api/v1/users/",
        json={
            "username": f"raguser-{suffix}",
            "email": email,
            "password": password,
        },
    )
    response = client.post(
        "/api/v1/auth/login",
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
        "/api/v1/rag/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", b"hello rag", "text/plain")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == DOCUMENT_STATUS_QUEUED
    assert payload["processing_task_id"] == "task-rag-upload-1"
    assert payload["chunks_count"] == 0
    assert payload["file_type"] == "txt"

    document = db_session.get(Document, payload["id"])
    assert document is not None
    assert document.status == DOCUMENT_STATUS_QUEUED
    assert document.processing_task_id == "task-rag-upload-1"
    assert document.owner_id is not None
    assert document.file_type == "txt"


def test_query_knowledge_base_uses_current_user_scope(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "query")
    user_id = int(
        client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    )

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
                            choices=[
                                SimpleNamespace(
                                    message=SimpleNamespace(content="基于当前用户文档的回答")
                                )
                            ],
                            usage=SimpleNamespace(
                                prompt_tokens=5, completion_tokens=7, total_tokens=12
                            ),
                        )

        return DummyClient()

    monkeypatch.setattr(RAGService, "retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr("app.api.routers.rag.get_llm_client", fake_get_llm_client)

    response = client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "我的知识库里有什么？", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "基于当前用户文档的回答"
    assert payload["source_chunks"] == ["只属于当前用户的知识片段"]


def test_worker_requeues_owned_document_and_returns_task_status(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "worker")
    user_id = int(
        client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    )

    document = Document(
        owner_id=user_id,
        filename="retry.txt",
        content="retry me",
        status=DOCUMENT_STATUS_READY,
        chunks_count=2,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    class DummyTask:
        id = "task-rag-worker-1"

    class DummyAsyncResult:
        status = "PROGRESS"
        info = {"step": "processing_document", "current": 1, "total": 1}

    monkeypatch.setattr(
        "app.api.routers.worker.process_document_task.delay",
        lambda document_id: DummyTask(),
    )
    monkeypatch.setattr(
        "app.api.routers.worker.celery_app.AsyncResult",
        lambda task_id: DummyAsyncResult(),
    )

    process_response = client.post(
        "/api/v1/worker/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"document_id": document.id},
    )
    assert process_response.status_code == 200
    process_payload = process_response.json()
    assert process_payload["task_id"] == "task-rag-worker-1"
    assert process_payload["status"] == DOCUMENT_STATUS_QUEUED

    db_session.expire_all()
    updated_document = db_session.get(Document, document.id)
    assert updated_document.processing_task_id == "task-rag-worker-1"
    assert updated_document.status == DOCUMENT_STATUS_QUEUED

    status_response = client.get(
        "/api/v1/worker/status/task-rag-worker-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["result"] == {
        "step": "processing_document",
        "current": 1,
        "total": 1,
    }


def test_upload_md_document(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "md-upload")

    class DummyTask:
        id = "task-rag-md-1"

    monkeypatch.setattr(
        "app.api.routers.rag.process_document_task.delay",
        lambda document_id: DummyTask(),
    )

    response = client.post(
        "/api/v1/rag/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("readme.md", b"# Title\n\nSome markdown content.", "text/markdown")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["file_type"] == "md"
    assert payload["status"] == DOCUMENT_STATUS_QUEUED

    document = db_session.get(Document, payload["id"])
    assert document.file_type == "md"
    assert "Title" in document.content


def test_upload_pdf_document(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "pdf-upload")

    import io

    from fpdf import FPDF

    buf = io.BytesIO()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, text="Project Orion RAG Test", new_x="LMARGIN", new_y="NEXT")
    pdf.output(buf)
    pdf_bytes = buf.getvalue()

    class DummyTask:
        id = "task-rag-pdf-1"

    monkeypatch.setattr(
        "app.api.routers.rag.process_document_task.delay",
        lambda document_id: DummyTask(),
    )

    response = client.post(
        "/api/v1/rag/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["file_type"] == "pdf"
    assert payload["status"] == DOCUMENT_STATUS_QUEUED

    document = db_session.get(Document, payload["id"])
    assert document.file_type == "pdf"
    assert "Project Orion" in document.content


def test_upload_unsupported_format(client):
    token = _create_user_and_login(client, "bad-fmt")

    response = client.post(
        "/api/v1/rag/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("image.png", b"fake png data", "image/png")},
    )

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_empty_pdf(client):
    token = _create_user_and_login(client, "empty-pdf")

    import io

    from fpdf import FPDF

    buf = io.BytesIO()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.output(buf)

    response = client.post(
        "/api/v1/rag/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.pdf", buf.getvalue(), "application/pdf")},
    )

    assert response.status_code == 400
    assert "no extractable text" in response.json()["detail"].lower()


def test_rag_query_stream_returns_sse(client, monkeypatch):
    token = _create_user_and_login(client, "stream")

    class FakeChunk:
        content = "streamed reply chunk"

    async def fake_retrieve(_self, *, query=None, owner_id=None, top_k=None):
        return [FakeChunk()]

    async def fake_stream_create(**kwargs):
        async def gen():
            chunk = type(
                "C",
                (),
                {
                    "choices": [
                        type(
                            "Ch",
                            (),
                            {"delta": type("D", (), {"content": "Hello from RAG stream"})()},
                        )()
                    ]
                },
            )()
            yield chunk

        return gen()

    monkeypatch.setattr(RAGService, "retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(
        "app.api.routers.rag.get_llm_client",
        lambda: type(
            "C",
            (),
            {
                "chat": type(
                    "Ch",
                    (),
                    {"completions": type("Co", (), {"create": staticmethod(fake_stream_create)})()},
                )()
            },
        )(),
    )

    with client.stream(
        "POST",
        "/api/v1/rag/query/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "test", "top_k": 3},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"


def test_rag_query_stream_no_chunks(client, monkeypatch, db_session):
    token = _create_user_and_login(client, "stream-empty")

    async def fake_retrieve_empty(*a, **kw):
        return []

    monkeypatch.setattr(RAGService, "retrieve_relevant_chunks", fake_retrieve_empty)

    with client.stream(
        "POST",
        "/api/v1/rag/query/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "test", "top_k": 3},
    ) as resp:
        assert resp.status_code == 200
        content = resp.read().decode("utf-8")
        assert "暂无已处理" in content or "data:" in content
