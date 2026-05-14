"""
RAG 服务层单元测试 (直接调用 Service 而非走 HTTP)
"""
import asyncio
import pytest
from unittest.mock import patch

from app.models.document import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PROCESSING,
    DOCUMENT_STATUS_QUEUED,
    DOCUMENT_STATUS_READY,
    Document,
)
from app.services.rag_service import RAGService

_owner_counter = 99000


def _next_owner():
    global _owner_counter
    _owner_counter += 1
    return _owner_counter


class TestRAGDocumentCreate:
    def test_create_document_record(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="test.txt", content="hello world", owner_id=owner)
        assert doc.id is not None
        assert doc.filename == "test.txt"
        assert doc.status == DOCUMENT_STATUS_QUEUED
        assert doc.chunks_count == 0

    def test_attach_processing_task(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="a.txt", content="c", owner_id=owner)
        updated = svc.attach_processing_task(document_id=doc.id, owner_id=owner, task_id="task-123")
        assert updated.processing_task_id == "task-123"
        assert updated.status == DOCUMENT_STATUS_QUEUED

    def test_attach_processing_task_wrong_owner_raises(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="a.txt", content="c", owner_id=owner)
        with pytest.raises(ValueError):
            svc.attach_processing_task(document_id=doc.id, owner_id=99999, task_id="task-x")


class TestRAGDocumentQuery:
    def test_list_documents_for_user(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        svc.create_document_record(filename="a.txt", content="a", owner_id=owner)
        svc.create_document_record(filename="b.txt", content="b", owner_id=owner)
        docs = svc.list_documents_for_user(owner_id=owner)
        assert len(docs) == 2

    def test_list_documents_user_isolation(self, db_session):
        owner_a = _next_owner()
        owner_b = _next_owner()
        svc = RAGService(db_session)
        svc.create_document_record(filename="user1.txt", content="1", owner_id=owner_a)
        svc.create_document_record(filename="user2.txt", content="2", owner_id=owner_b)
        assert len(svc.list_documents_for_user(owner_id=owner_a)) == 1
        assert len(svc.list_documents_for_user(owner_id=owner_b)) == 1

    def test_list_documents_empty_for_new_owner(self, db_session):
        svc = RAGService(db_session)
        docs = svc.list_documents_for_user(owner_id=99999)
        assert docs == []

    def test_get_document_for_user(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="f.txt", content="c", owner_id=owner)
        found = svc.get_document_for_user(document_id=doc.id, owner_id=owner)
        assert found is not None
        assert found.filename == "f.txt"

    def test_get_document_not_found(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        assert svc.get_document_for_user(document_id=99999, owner_id=owner) is None

    def test_get_document_by_task_id(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="t.txt", content="c", owner_id=owner)
        svc.attach_processing_task(document_id=doc.id, owner_id=owner, task_id="celery-abc")
        found = svc.get_document_by_task_id_for_user(task_id="celery-abc", owner_id=owner)
        assert found is not None
        assert found.id == doc.id

    def test_has_ready_documents_false_initially(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        svc.create_document_record(filename="q.txt", content="q", owner_id=owner)
        assert svc.has_ready_documents(owner_id=owner) is False


class TestRAGDocumentStatusTransitions:
    def test_mark_document_processing(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="p.txt", content="p", owner_id=owner)
        updated = svc.mark_document_processing(document_id=doc.id)
        assert updated.status == DOCUMENT_STATUS_PROCESSING

    def test_mark_document_failed(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="f.txt", content="f", owner_id=owner)
        svc.mark_document_failed(document_id=doc.id, error_message="embedding error")
        db_session.refresh(doc)
        assert doc.status == DOCUMENT_STATUS_FAILED
        assert doc.error_message == "embedding error"

    def test_requeue_document(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="r.txt", content="r", owner_id=owner)
        updated = svc.requeue_document(document_id=doc.id, owner_id=owner, task_id="retry-1")
        assert updated.status == DOCUMENT_STATUS_QUEUED
        assert updated.processing_task_id == "retry-1"
        assert updated.error_message is None

    def test_requeue_document_wrong_owner_raises(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="r2.txt", content="r2", owner_id=owner)
        with pytest.raises(ValueError):
            svc.requeue_document(document_id=doc.id, owner_id=99999, task_id="retry-x")


class TestRAGDocumentProcessing:
    def test_process_document_empty_content(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="empty.txt", content="", owner_id=owner)
        processed = asyncio.run(svc.process_document(document_id=doc.id))
        assert processed.status == DOCUMENT_STATUS_READY
        assert processed.chunks_count == 0

    def test_process_document_with_content(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        content = "人工智能是计算机科学的一个分支。\n它致力于创造能够模拟人类智能的系统。"
        doc = svc.create_document_record(filename="ai.txt", content=content, owner_id=owner)

        async def fake_embeddings(texts):
            return [[0.1] * 1024 for _ in texts]

        with patch.object(svc, "get_embeddings", side_effect=fake_embeddings):
            processed = asyncio.run(svc.process_document(document_id=doc.id))
        assert processed.status == DOCUMENT_STATUS_READY
        assert processed.chunks_count > 0
