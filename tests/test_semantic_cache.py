"""语义缓存单元测试"""

import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.qa_cache import QACacheEntry
from app.models.user import User
from app.services import semantic_cache
from app.services.semantic_cache import (
    get_cache_stats,
    invalidate_user_cache,
    is_cacheable_question,
    lookup_semantic_cache,
    store_semantic_cache,
)

DIM = 1024


def _vec(unit_index: int) -> list:
    """正交单位向量，相似度可控（相同=1，正交=0）"""
    v = [0.0] * DIM
    v[unit_index] = 1.0
    return v


def _vec_mix(cosine: float) -> list:
    """与 _vec(0) 的余弦相似度恰为 cosine 的单位向量。"""
    v = [0.0] * DIM
    v[0] = cosine
    v[1] = (1 - cosine * cosine) ** 0.5
    return v


def _add_entry(db, *, user_id=1, question="问题A", answer="回答A", embedding=None):
    db.add(
        QACacheEntry(
            user_id=user_id,
            question=question,
            answer=answer,
            embedding=embedding or _vec(0),
            model_name="m",
            prompt_tokens=100,
            completion_tokens=50,
            original_cost_cny=0.001,
        )
    )
    db.commit()


@pytest.fixture(autouse=True)
def _restore_cache_settings():
    old_enabled = settings.SEMANTIC_CACHE_ENABLED
    old_threshold = settings.SEMANTIC_CACHE_THRESHOLD
    old_candidate = settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD
    yield
    settings.SEMANTIC_CACHE_ENABLED = old_enabled
    settings.SEMANTIC_CACHE_THRESHOLD = old_threshold
    settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD = old_candidate


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


class TestCacheableQuestion:
    @pytest.mark.parametrize(
        "question",
        [
            "问题A",
            "BERT 的预训练任务是什么？",
            "帮我总结 Transformer 的自注意力机制",
        ],
    )
    def test_simple_questions_are_cacheable(self, question):
        assert is_cacheable_question(question) is True

    @pytest.mark.parametrize(
        "question",
        [
            # 线上真实误命中：短问题 + 追加一句，92% 相似度复用了短答案
            "哪份 JD 明确提出 985/211 学历要求？还有哪些岗位写了实习时长或到岗频率要求？",
            "问题A？问题B？",
            "对比 A 和 B，并分别给出投递优先级",
            "总结这篇论文，顺便列出实验缺陷",
            "长" * 81,
            "第一行问题\n第二行问题",
        ],
    )
    def test_multi_intent_or_long_questions_are_not_cacheable(self, question):
        assert is_cacheable_question(question) is False


class TestStoreAndLookup:
    def test_multi_intent_question_never_cached(self, db_session):
        question = "哪份 JD 明确提出 985/211 学历要求？还有哪些岗位写了实习时长或到岗频率要求？"
        asyncio.run(
            store_semantic_cache(db_session, 1, question, "只答了一半的答案", "m", 100, 50, 0.001)
        )
        assert db_session.query(QACacheEntry).count() == 0
        assert asyncio.run(lookup_semantic_cache(db_session, 1, question)) is None

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

    def test_below_candidate_threshold_misses(self, db_session):
        # 候选阈值高于可能达到的最大相似度 1.0 → 连灰区校验都不触发
        settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD = 1.5
        asyncio.run(store_semantic_cache(db_session, 1, "问题A", "回答A", "m", 100, 50, 0.001))
        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题A"))
        assert hit is None

    def test_gray_zone_hits_when_judge_says_same(self, db_session, monkeypatch):
        _add_entry(db_session)

        async def fake_embed(db, text):
            return _vec_mix(0.90)

        async def fake_judge(db, user_id, cached_question, new_question):
            return True

        monkeypatch.setattr(semantic_cache, "_embed_query", fake_embed)
        monkeypatch.setattr(semantic_cache, "_judge_same_question", fake_judge)

        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题B"))
        assert hit is not None
        entry, similarity = hit
        assert entry.answer == "回答A"
        assert similarity == pytest.approx(0.90)

    def test_gray_zone_misses_when_judge_says_different(self, db_session, monkeypatch):
        _add_entry(db_session)

        async def fake_embed(db, text):
            return _vec_mix(0.93)

        async def fake_judge(db, user_id, cached_question, new_question):
            return False

        monkeypatch.setattr(semantic_cache, "_embed_query", fake_embed)
        monkeypatch.setattr(semantic_cache, "_judge_same_question", fake_judge)

        assert asyncio.run(lookup_semantic_cache(db_session, 1, "问题B")) is None

    def test_high_similarity_skips_judge(self, db_session, monkeypatch):
        _add_entry(db_session)

        async def fake_embed(db, text):
            return _vec(0)

        async def boom(*args, **kwargs):
            raise AssertionError("高置信度命中不应调用校验")

        monkeypatch.setattr(semantic_cache, "_embed_query", fake_embed)
        monkeypatch.setattr(semantic_cache, "_judge_same_question", boom)

        hit = asyncio.run(lookup_semantic_cache(db_session, 1, "问题B"))
        assert hit is not None


class TestJudgeSameQuestion:
    @pytest.mark.parametrize(("reply", "expected"), [("是", True), ("是。", True), ("否", False)])
    def test_parses_judge_reply(self, db_session, monkeypatch, reply, expected):
        class FakeCompletions:
            async def create(self, **kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=1, total_tokens=11),
                )

        info = SimpleNamespace(
            model_name="m",
            client=SimpleNamespace(
                api_key="fake",
                chat=SimpleNamespace(completions=FakeCompletions()),
            ),
        )
        monkeypatch.setattr("app.services.llm_service.get_llm_client", lambda user=None: info)
        monkeypatch.setattr(
            "app.services.llm_observability_service.create_llm_call_log",
            lambda *args, **kwargs: None,
        )

        result = asyncio.run(semantic_cache._judge_same_question(db_session, 1, "A", "B"))
        assert result is expected


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


class TestCacheInvalidation:
    """知识库变更后旧答案必须作废：按用户整体失效，且不误伤其他用户。"""

    @pytest.fixture
    def cache_users(self, db_session):
        for uid in (98001, 98002):
            if db_session.get(User, uid) is None:
                db_session.add(
                    User(
                        id=uid,
                        username=f"cache_user_{uid}",
                        email=f"cache_user_{uid}@example.com",
                        hashed_password="hashed",
                        is_active=True,
                    )
                )
        db_session.commit()
        return 98001, 98002

    def _add_entry(self, db, user_id, index):
        db.add(
            QACacheEntry(
                user_id=user_id,
                question=f"问题{index}",
                answer=f"回答{index}",
                embedding=_vec(index),
                model_name="m",
            )
        )

    def test_removes_only_target_user_entries(self, db_session, cache_users):
        user_a, user_b = cache_users
        self._add_entry(db_session, user_a, 0)
        self._add_entry(db_session, user_a, 1)
        self._add_entry(db_session, user_b, 2)
        db_session.commit()

        assert invalidate_user_cache(db_session, user_a) == 2

        remaining = db_session.query(QACacheEntry).all()
        assert [entry.user_id for entry in remaining] == [user_b]

    def test_returns_zero_when_nothing_cached(self, db_session, cache_users):
        assert invalidate_user_cache(db_session, cache_users[0]) == 0

    def test_none_user_id_is_noop(self, db_session):
        db_session.add(
            QACacheEntry(user_id=None, question="q", answer="a", embedding=_vec(3), model_name="m")
        )
        db_session.commit()

        assert invalidate_user_cache(db_session, None) == 0
        assert db_session.query(QACacheEntry).count() == 1
