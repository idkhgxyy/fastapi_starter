"""
RAG 服务层单元测试 (直接调用 Service 而非走 HTTP)
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.models.document import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PROCESSING,
    DOCUMENT_STATUS_QUEUED,
    DOCUMENT_STATUS_READY,
    Document,
    DocumentChunk,
)
from app.models.qa_cache import QACacheEntry
from app.models.user import User
from app.services.rag_service import (
    SUMMARY_INJECTION_PREVIEW_CHARS,
    RAGService,
    is_global_query,
)

_owner_counter = 99000

# 测试用户池上限。documents.owner_id 有外键约束，Postgres 下会强制校验
# （sqlite 默认不校验，所以这类问题只在 Postgres 上暴露）。
# 池子耗尽的症状是一堆看不懂的 ForeignKeyViolation，所以这里显式报错。
_MAX_TEST_USER_ID = 99100


def _ensure_test_users_exist(db):
    existing = set(
        row[0]
        for row in db.execute(
            text("SELECT id FROM users WHERE id >= :min_id"),
            {"min_id": 99001},
        ).fetchall()
    )
    for uid in range(99001, _MAX_TEST_USER_ID + 1):
        if uid not in existing:
            db.add(
                User(
                    id=uid,
                    username=f"ragtest_{uid}",
                    email=f"ragtest_{uid}@example.com",
                    hashed_password="hashed",
                    is_active=True,
                )
            )
    db.commit()


@pytest.fixture(autouse=True)
def _setup_rag_test_users(db_session):
    _ensure_test_users_exist(db_session)
    yield


def _next_owner():
    global _owner_counter
    _owner_counter += 1
    if _owner_counter > _MAX_TEST_USER_ID:
        raise RuntimeError(
            f"测试用户池已耗尽（上限 {_MAX_TEST_USER_ID}）：请调大 _MAX_TEST_USER_ID"
        )
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

    def test_process_document_prefixes_chunks_with_title(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        content = (
            "# 测试岗位\n\n"
            "## 岗位职责\n\n" + "负责后端服务开发与维护。" * 40 + "\n\n"
            "## 任职要求\n\n- 熟练掌握 Java 与 Spring Boot\n"
        )
        doc = svc.create_document_record(filename="jd.md", content=content, owner_id=owner)

        async def fake_embeddings(texts):
            return [[0.1] * 1024 for _ in texts]

        with patch.object(svc, "get_embeddings", side_effect=fake_embeddings):
            asyncio.run(svc.process_document(document_id=doc.id))

        chunks = (
            db_session.query(DocumentChunk)
            .filter_by(document_id=doc.id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
        assert len(chunks) > 1
        assert all(chunk.content.lstrip().startswith("# 测试岗位") for chunk in chunks)
        requirement_chunk = next(c for c in chunks if "## 任职要求" in c.content)
        assert requirement_chunk.content.lstrip().startswith("# 测试岗位")


def _add_document(db, *, owner, filename, summary=None, status=DOCUMENT_STATUS_READY):
    document = Document(
        owner_id=owner,
        filename=filename,
        file_type="md",
        content="文档正文占位",
        status=status,
        chunks_count=1,
        summary=summary,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


class TestGlobalQueryDetection:
    def test_marks_global_questions(self):
        for query in (
            "串讲四篇论文",
            "帮我总结一下知识库",
            "这几篇有什么区别",
            "这两个岗位的技术栈要求有什么差异",
            "哪份 JD 明确提出 985/211 学历要求",
            "哪些岗位明确要求 Python",
            "我都有哪些资料",
            "整体梳理一遍",
        ):
            assert is_global_query(query) is True

    def test_leaves_specific_questions_alone(self):
        for query in (
            "Transformer 为什么用自注意力",
            "BERT 的预训练任务是什么",
            "如何配置 Redis 连接",
        ):
            assert is_global_query(query) is False


class TestMarkdownChunking:
    def test_requirements_heading_is_not_left_at_chunk_tail(self):
        svc = RAGService(None)
        content = (
            "# 测试岗位\n\n"
            "- 公司：测试\n"
            "- 链接：https://example.com/" + "x" * 250 + "\n\n"
            "## 岗位职责\n\n" + "负责后端服务开发与维护。" * 40 + "\n\n"
            "## 任职要求\n\n- 熟练掌握 Java 与 Spring Boot\n- 要求 985/211 本科\n"
        )
        chunks = svc.text_splitter.split_text(content)

        assert any(chunk.startswith("## 任职要求") for chunk in chunks)
        assert not any(chunk.rstrip().endswith("## 任职要求") for chunk in chunks)
        requirement_chunk = next(chunk for chunk in chunks if chunk.startswith("## 任职要求"))
        assert "985/211" in requirement_chunk


class TestKnowledgeContextBuild:
    """摘要兜底：全局问题 / 检索为空时注入摘要，具体问题只给原文片段。"""

    def _service_with_chunks(self, db_session, chunks):
        svc = RAGService(db_session)

        # 直接挂在实例上（不需要 self），避免走真实 embedding
        async def fake_retrieve(**kwargs):
            return chunks

        svc.retrieve_relevant_chunks = fake_retrieve
        return svc

    def test_global_query_injects_summaries_even_with_chunks(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="Transformer.pdf", summary="讲自注意力")
        _add_document(db_session, owner=owner, filename="BERT.pdf", summary="讲双向预训练")
        chunk = SimpleNamespace(
            content="原文片段A", document=SimpleNamespace(filename="Transformer.pdf")
        )
        svc = self._service_with_chunks(db_session, [chunk])

        result = asyncio.run(
            svc.build_knowledge_context(query="串讲四篇论文", owner_id=owner, top_k=3)
        )

        assert result.context is not None
        assert "文档摘要" in result.context
        assert "讲自注意力" in result.context and "讲双向预训练" in result.context
        assert "原文片段A" in result.context
        assert result.total_ready_documents == 2
        assert len(result.summary_documents) == 2

    def test_specific_query_skips_summaries(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="BERT.pdf", summary="讲双向预训练")
        chunk = SimpleNamespace(content="原文片段B", document=SimpleNamespace(filename="BERT.pdf"))
        svc = self._service_with_chunks(db_session, [chunk])

        result = asyncio.run(
            svc.build_knowledge_context(query="BERT 的预训练任务是什么", owner_id=owner, top_k=3)
        )

        assert result.context is not None
        assert "原文片段B" in result.context
        assert "文档摘要" not in result.context
        assert result.summary_documents == []

    def test_no_chunks_falls_back_to_summaries(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="CoT.pdf", summary="讲思维链提示")
        svc = self._service_with_chunks(db_session, [])

        result = asyncio.run(
            svc.build_knowledge_context(query="随便问点什么", owner_id=owner, top_k=3)
        )

        assert "讲思维链提示" in result.context
        assert "没有检索到与问题直接相关的原文片段" in result.context

    def test_no_documents_returns_empty_context(self, db_session):
        owner = _next_owner()
        svc = self._service_with_chunks(db_session, [])

        result = asyncio.run(svc.build_knowledge_context(query="串讲讲", owner_id=owner, top_k=3))

        assert result.context is None
        assert result.total_ready_documents == 0

    def test_documents_without_summary_are_not_injected(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="待摘要.pdf", summary=None)
        svc = self._service_with_chunks(db_session, [])

        result = asyncio.run(svc.build_knowledge_context(query="串讲讲", owner_id=owner, top_k=3))

        assert result.context is None
        assert result.summary_documents == []
        assert result.total_ready_documents == 1

    def test_summary_preview_is_truncated(self, db_session):
        owner = _next_owner()
        _add_document(
            db_session,
            owner=owner,
            filename="长文.pdf",
            summary="很长" * SUMMARY_INJECTION_PREVIEW_CHARS,
        )
        svc = self._service_with_chunks(db_session, [])

        result = asyncio.run(svc.build_knowledge_context(query="串讲讲", owner_id=owner, top_k=3))

        assert "…" in result.context
        injected = result.context.split("《长文.pdf》：")[1].split("\n")[0]
        assert len(injected) == SUMMARY_INJECTION_PREVIEW_CHARS + 1

    def test_context_labels_chunk_source_filename(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="RAG.pdf", summary=None)
        chunk = SimpleNamespace(content="片段正文", document=SimpleNamespace(filename="RAG.pdf"))
        svc = self._service_with_chunks(db_session, [chunk])

        result = asyncio.run(
            svc.build_knowledge_context(query="RAG 是什么", owner_id=owner, top_k=3)
        )

        assert "来自《RAG.pdf》" in result.context

    def test_chunks_without_document_relation_do_not_crash(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="x.md", summary=None)
        svc = self._service_with_chunks(db_session, [SimpleNamespace(content="裸片段")])

        result = asyncio.run(svc.build_knowledge_context(query="细节问题", owner_id=owner, top_k=3))

        assert "裸片段" in result.context

    def test_retrieval_failure_still_falls_back_to_summaries(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="兜底.pdf", summary="摘要内容")
        svc = RAGService(db_session)

        async def boom(**kwargs):
            raise RuntimeError("embedding 服务不可用")

        svc.retrieve_relevant_chunks = boom

        result = asyncio.run(svc.build_knowledge_context(query="串讲讲", owner_id=owner, top_k=3))

        assert "摘要内容" in result.context
        assert result.chunks == []

    def test_source_labels_include_summary_documents(self, db_session):
        owner = _next_owner()
        _add_document(db_session, owner=owner, filename="A.pdf", summary="摘要A")
        chunk = SimpleNamespace(content="片段A", document=SimpleNamespace(filename="A.pdf"))
        svc = self._service_with_chunks(db_session, [chunk])

        result = asyncio.run(svc.build_knowledge_context(query="串讲讲", owner_id=owner, top_k=3))

        assert result.source_labels() == ["片段A", "《A.pdf》（文档摘要）"]


def _add_cache_entry(db, *, owner, index=0):
    vector = [0.0] * 1024
    vector[index] = 1.0
    db.add(
        QACacheEntry(
            user_id=owner,
            question="知识库变更前的旧问题",
            answer="旧答案",
            embedding=vector,
            model_name="m",
        )
    )
    db.commit()


class TestSemanticCacheInvalidation:
    """知识库真的变了才失效缓存：处理完成 / 删除 两个时点。"""

    def test_process_document_ready_invalidates_owner_cache(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="new.md", content="内容" * 20, owner_id=owner)
        _add_cache_entry(db_session, owner=owner)
        assert db_session.query(QACacheEntry).filter_by(user_id=owner).count() == 1

        async def fake_embeddings(texts):
            return [[0.1] * 1024 for _ in texts]

        with patch.object(svc, "get_embeddings", side_effect=fake_embeddings):
            asyncio.run(svc.process_document(document_id=doc.id))

        assert db_session.query(QACacheEntry).filter_by(user_id=owner).count() == 0

    def test_delete_document_invalidates_owner_cache(self, db_session):
        owner = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="del.md", content="内容", owner_id=owner)
        _add_cache_entry(db_session, owner=owner)

        svc.delete_document(document_id=doc.id, owner_id=owner)

        assert db_session.query(QACacheEntry).filter_by(user_id=owner).count() == 0

    def test_processing_does_not_touch_other_users_cache(self, db_session):
        owner = _next_owner()
        other = _next_owner()
        svc = RAGService(db_session)
        doc = svc.create_document_record(filename="mine.md", content="内容" * 20, owner_id=owner)
        _add_cache_entry(db_session, owner=other, index=1)

        async def fake_embeddings(texts):
            return [[0.1] * 1024 for _ in texts]

        with patch.object(svc, "get_embeddings", side_effect=fake_embeddings):
            asyncio.run(svc.process_document(document_id=doc.id))

        assert db_session.query(QACacheEntry).filter_by(user_id=other).count() == 1
