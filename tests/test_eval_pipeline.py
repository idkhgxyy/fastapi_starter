"""eval_pipeline 负例归因测试：分类器判定顺序 + DB 归因与校验证据交叉核对"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.core.config import settings
from app.models.llm_call_log import LLMCallLog
from app.models.qa_cache import QACacheEntry
from scripts.eval_pipeline import _attribute_negative, classify_negative_reject


def test_password_missing_raises_only_when_called(monkeypatch):
    """口令校验必须在调用时而非导入时：CI 无 EVAL_PASSWORD/.env，模块级 raise 会炸收集。"""
    import scripts.eval_pipeline as ep

    monkeypatch.delenv("EVAL_PASSWORD", raising=False)
    monkeypatch.delenv("SMOKE_PASSWORD", raising=False)
    monkeypatch.setattr(ep, "_env_value", lambda key: "")
    with pytest.raises(SystemExit):
        ep._password()


DIM = 1024
ANNUAL = "员工入职满一年后有几天带薪年假？"
SICK = "员工每年有多少天带薪病假？"


def _base_vec() -> list:
    v = [0.0] * DIM
    v[0] = 1.0
    return v


def _vec(cosine: float) -> list:
    """与 _base_vec() 余弦相似度恰为 cosine 的单位向量。"""
    v = [0.0] * DIM
    v[0] = cosine
    v[1] = (1 - cosine * cosine) ** 0.5
    return v


@pytest.fixture(autouse=True)
def _pin_thresholds():
    old = (settings.SEMANTIC_CACHE_THRESHOLD, settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD)
    settings.SEMANTIC_CACHE_THRESHOLD = 0.95
    settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD = 0.80
    yield
    settings.SEMANTIC_CACHE_THRESHOLD, settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD = old


@pytest.fixture(autouse=True)
def _clean_tables(db_session):
    yield
    db_session.query(QACacheEntry).delete()
    db_session.query(LLMCallLog).delete()
    db_session.commit()


class TestClassifyNegativeReject:
    @pytest.mark.parametrize(
        "similarity,cached,negative,has_sources,expected",
        [
            (0.79, ANNUAL, SICK, True, "below_candidate"),
            # 中文实体替换：数字/专名守卫都是空集，灰区只能靠 LLM
            (0.85, ANNUAL, SICK, True, "llm_judge"),
            # 同一对进直通带：零静态防线，本应直接命中
            (0.97, ANNUAL, SICK, True, "direct_hit_band"),
            (0.97, "J106366 要求哪些语言？", "J101366 要求哪些语言？", True, "guard"),
            # 英文专名变化即使 ≥0.95 也强制校验
            (0.97, "BERT 是什么？", "Transformer 是什么？", True, "llm_judge"),
            (0.97, "问题A", "问题A", False, "guard"),
            (0.96, "问题A", "问题A", True, "direct_hit_band"),
            # 候选下限含等号
            (0.80, "问题A", "问题A", True, "llm_judge"),
        ],
    )
    def test_classify(self, similarity, cached, negative, has_sources, expected):
        assert (
            classify_negative_reject(similarity, cached, negative, has_sources=has_sources)
            == expected
        )


def _add_entry(db, question, vector, *, source_chunks=None):
    db.add(
        QACacheEntry(
            user_id=1,
            question=question,
            answer="答",
            embedding=vector,
            source_chunks=source_chunks,
            model_name="m",
            prompt_tokens=100,
            completion_tokens=50,
            original_cost_cny=0.001,
        )
    )
    db.commit()


class TestAttributeNegative:
    def test_gray_zone_with_judge_evidence(self, db_session):
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        _add_entry(db_session, ANNUAL, _base_vec(), source_chunks=["片段"])
        _add_entry(db_session, SICK, _vec(0.90))
        db_session.add(
            LLMCallLog(
                user_id=1,
                endpoint="/semantic-cache/verify",
                model_name="m",
                prompt=f"问题A：{ANNUAL}\n问题B：{SICK}",
                response="否",
            )
        )
        db_session.commit()
        result = _attribute_negative(db_session, 1, SICK, True, started)
        assert result["negative_reject_reason"] == "llm_judge"
        assert result["negative_similarity"] == 0.9
        assert result["negative_judge_responses"] == ["否"]

    def test_judge_evidence_limited_to_current_run(self, db_session):
        """评测账号日志跨轮累积：上一轮的响应（哪怕是「是」）不能混进本轮证据。"""
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        _add_entry(db_session, ANNUAL, _base_vec(), source_chunks=["片段"])
        _add_entry(db_session, SICK, _vec(0.90))
        prompt = f"问题A：{ANNUAL}\n问题B：{SICK}"
        db_session.add_all(
            [
                LLMCallLog(
                    user_id=1,
                    endpoint="/semantic-cache/verify",
                    model_name="m",
                    prompt=prompt,
                    response="是",
                    created_at=started - timedelta(hours=1),
                ),
                LLMCallLog(
                    user_id=1,
                    endpoint="/semantic-cache/verify",
                    model_name="m",
                    prompt=prompt,
                    response="否",
                ),
            ]
        )
        db_session.commit()
        result = _attribute_negative(db_session, 1, SICK, True, started)
        assert result["negative_judge_responses"] == ["否"]
        assert result["negative_reject_reason"] == "llm_judge"

    def test_gray_zone_without_judge_log_is_other(self, db_session):
        """进了灰区却没有校验记录：judge 故障被静默按不命中，不能算安全拒绝。"""
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        _add_entry(db_session, ANNUAL, _base_vec(), source_chunks=["片段"])
        _add_entry(db_session, SICK, _vec(0.90))
        result = _attribute_negative(db_session, 1, SICK, True, started)
        assert result["negative_reject_reason"] == "other"
        assert result["negative_similarity"] == 0.9

    def test_numeric_guard(self, db_session):
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        base = "J106366 这个岗位要求掌握哪些编程语言？"
        negative = "J101366 这个岗位要求掌握哪些编程语言？"
        _add_entry(db_session, base, _base_vec(), source_chunks=["片段"])
        _add_entry(db_session, negative, _vec(0.97))
        result = _attribute_negative(db_session, 1, negative, True, started)
        assert result["negative_reject_reason"] == "guard"
        assert result["negative_similarity"] == 0.97

    def test_below_candidate(self, db_session):
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        _add_entry(db_session, ANNUAL, _base_vec(), source_chunks=["片段"])
        _add_entry(db_session, SICK, _vec(0.5))
        result = _attribute_negative(db_session, 1, SICK, True, started)
        assert result["negative_reject_reason"] == "below_candidate"
        assert result["negative_similarity"] == 0.5

    def test_false_hit_uses_reembed_fallback(self, db_session, monkeypatch):
        """负例误命中时自身不落库，向量走重嵌回退，仍要给出相似度供诊断。"""
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        _add_entry(db_session, ANNUAL, _base_vec(), source_chunks=["片段"])

        async def fake_embed(db, text):
            return _vec(0.97)

        monkeypatch.setattr("scripts.eval_pipeline._embed_query", fake_embed)
        result = _attribute_negative(db_session, 1, SICK, False, started)
        assert result["negative_reject_reason"] == "hit"
        assert result["negative_similarity"] == 0.97

    def test_result_json_serializable_with_float32(self, db_session, monkeypatch):
        """pgvector 读回 float32：不显式 cast 成 Python float 会炸 report.json 落盘。"""
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        _add_entry(db_session, ANNUAL, _base_vec(), source_chunks=["片段"])
        _add_entry(db_session, SICK, _vec(0.90))
        monkeypatch.setattr(
            "scripts.eval_pipeline._cosine_similarity", lambda a, b: np.float32(0.9)
        )
        result = _attribute_negative(db_session, 1, SICK, True, started)
        json.dumps(result, ensure_ascii=False)
        assert result["negative_similarity"] == 0.9
