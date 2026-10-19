"""闲时批量摘要任务单元测试"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.document import DOCUMENT_STATUS_READY, Document
from app.worker.celery_app import celery_app
from app.worker.tasks import _summarize_document, summarize_pending_documents


@pytest.fixture(autouse=True)
def _clean_documents(db_session):
    """每个测试结束后清空文档表，避免内存库数据跨测试残留"""
    yield
    db_session.query(Document).delete()
    db_session.commit()


class TestBeatSchedule:
    def test_off_peak_schedule_registered(self):
        entry = celery_app.conf.beat_schedule.get("summarize-pending-documents-off-peak")
        assert entry is not None
        assert entry["task"] == "app.worker.tasks.summarize_pending_documents"
        crontab = entry["schedule"]
        # 北京时间 22:30 触发，落在百炼闲时窗口（22:00~次日 8:00）
        assert crontab.hour == {22}
        assert crontab.minute == {30}

    def test_task_registered(self):
        assert "app.worker.tasks.summarize_pending_documents" in celery_app.tasks


class TestSummarizeDocument:
    @pytest.fixture
    def ready_doc(self, db_session):
        doc = Document(
            owner_id=None,
            filename="test.md",
            file_type="md",
            content="# 技术文档\n\n这是一个基于 FastAPI 的个人知识库系统，使用 pgvector 做向量检索。",
            status=DOCUMENT_STATUS_READY,
        )
        db_session.add(doc)
        db_session.commit()
        return doc

    def test_summarize_success(self, db_session, ready_doc, monkeypatch):
        from types import SimpleNamespace

        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        message = SimpleNamespace(content="这是一个 FastAPI 知识库系统文档。", tool_calls=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)

        class FakeCompletions:
            async def create(self, **kwargs):
                assert "摘要" in kwargs["messages"][0]["content"]
                return response

        info = SimpleNamespace(
            client=SimpleNamespace(api_key="fake-key", chat=SimpleNamespace(completions=FakeCompletions())),
            model_name="fake-model",
        )
        monkeypatch.setattr(
            "app.services.llm_service.get_llm_client", lambda user: info
        )

        summary = asyncio_run(_summarize_document(db_session, ready_doc))
        assert "FastAPI" in summary

    def test_summarize_no_llm_raises(self, db_session, ready_doc, monkeypatch):
        no_key_info = SimpleNamespace(
            client=SimpleNamespace(api_key=""), model_name="x"
        )
        monkeypatch.setattr(
            "app.services.llm_service.get_llm_client", lambda user: no_key_info
        )
        # 无 Key 且无本地降级（mock 模式）时应抛错
        import app.services.llm_service as llm_service

        monkeypatch.setattr(llm_service, "_build_fallback_info", lambda: None)
        with pytest.raises(Exception):
            asyncio_run(_summarize_document(db_session, ready_doc))


class TestPendingScan:
    def test_only_scans_ready_without_summary(self, db_session):
        db_session.add(
            Document(
                owner_id=None,
                filename="a.md",
                file_type="md",
                content="content",
                status=DOCUMENT_STATUS_READY,
                summary=None,
            )
        )
        db_session.add(
            Document(
                owner_id=None,
                filename="b.md",
                file_type="md",
                content="content",
                status=DOCUMENT_STATUS_READY,
                summary="已有摘要",
            )
        )
        db_session.commit()

        pending = (
            db_session.query(Document)
            .filter(Document.status == DOCUMENT_STATUS_READY, Document.summary.is_(None))
            .all()
        )
        assert [d.filename for d in pending] == ["a.md"]


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
