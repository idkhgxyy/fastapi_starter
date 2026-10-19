"""语义缓存单元测试"""

import asyncio

import pytest

from app.core.config import settings
from app.models.qa_cache import QACacheEntry
from app.services import semantic_cache
from app.services.semantic_cache import (
    get_cache_stats,
    lookup_semantic_cache,
    store_semantic_cache,
)

DIM = 1024


def _vec(unit_index: int) -> list:
    """正交单位向量，相似度可控（相同=1，正交=0）"""
    v = [0.0] * DIM
    v[unit_index] = 1.0
    return v


@pytest.fixture(autouse=True)
def _restore_cache_settings():
    old_enabled = settings.SEMANTIC_CACHE_ENABLED
    old_threshold = settings.SEMANTIC_CACHE_THRESHOLD
    yield
    settings.SEMANTIC_CACHE_ENABLED = old_enabled
    settings.SEMANTIC_CACHE_THRESHOLD = old_threshold


@pytest.fixture(autouse=True)
def _clean_cache(db_session):
    """每个测试结束后清空缓存表，避免内存库数据跨测试残留"""
    yield
    db_session.query(QACacheEntry).delete()
    db_session.commit()


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    """用问题文本映射到固定正交向量，避免依赖 Ollama"""

    class FakeRAGService:
        def __init__(self, db):
            pass

        async def get_embeddings(self, texts):
            mapping = {"问题A": _vec(0), "问题B": _vec(1)}
            return [mapping.get(t, _vec(hash(t) % DIM)) for t in texts]

    monkeypatch.setattr(semantic_cache, "RAGService", FakeRAGService)


class TestStoreAndLookup:
    def test_store_then_hit(self, db_session):
        asyncio.run(
            store_semantic_cache(
                db_session,
                1,
                "问题A",
                "回答A",
                "deepseek-v4.1-flash",
                1000,
                500,
                0.006,
            )
        )
        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题A"))
        assert hit is not None
        entry, similarity = hit
        assert entry.answer == "回答A"
        assert similarity == pytest.approx(1.0)
        assert entry.hit_count == 1

    def test_orthogonal_question_misses(self, db_session):
        asyncio.run(store_semantic_cache(db_session, 1, "问题A", "回答A", "m", 100, 50, 0.001))
        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题B"))
        assert hit is None

    def test_isolated_per_user(self, db_session):
        asyncio.run(
            store_semantic_cache(db_session, 1, "问题A", "用户1的回答", "m", 100, 50, 0.001)
        )
        # 用户 2 查同样的问题 → 命中不了用户 1 的条目（缓存表为空 → None）
        hit = asyncio.run(lookup_semantic_cache(db_session, 2, "问题A"))
        assert hit is None

    def test_disabled_cache_skips(self, db_session):
        settings.SEMANTIC_CACHE_ENABLED = False
        asyncio.run(store_semantic_cache(db_session, 1, "问题A", "回答A", "m", 100, 50, 0.001))
        assert db_session.query(QACacheEntry).count() == 0
        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题A"))
        assert hit is None

    def test_threshold_blocks_below_threshold(self, db_session):
        # 阈值高于可能达到的最大相似度 1.0 → 即使完全相同的问题也判为未命中
        settings.SEMANTIC_CACHE_THRESHOLD = 1.5
        asyncio.run(store_semantic_cache(db_session, 1, "问题A", "回答A", "m", 100, 50, 0.001))
        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题A"))
        assert hit is None


class TestCacheStats:
    def test_counts_hits_and_savings(self, db_session):
        db_session.add(
            QACacheEntry(
                user_id=1,
                question="q",
                answer="a",
                embedding=_vec(0),
                model_name="m",
                prompt_tokens=1000,
                completion_tokens=500,
                original_cost_cny=0.006,
                hit_count=3,
            )
        )
        db_session.commit()
        stats = get_cache_stats(db_session, 1)
        assert stats["cache_entries"] == 1
        assert stats["cache_hits"] == 3
        assert stats["cache_saved_cny"] == pytest.approx(0.018)

        other = get_cache_stats(db_session, 2)
        assert other["cache_hits"] == 0
