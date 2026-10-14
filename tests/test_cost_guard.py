"""成本熔断（cost_guard）单元测试"""

import pytest

from app.core.config import settings
from app.models.llm_call_log import LLMCallLog
from app.services.cost_guard import (
    BudgetStatus,
    check_budget,
    estimate_cost_cny,
    get_spent_cny,
)


@pytest.fixture
def _restore_budget():
    """保存/恢复 LLM_BUDGET_CNY，避免测试间互相污染"""
    old = settings.LLM_BUDGET_CNY
    yield
    settings.LLM_BUDGET_CNY = old


@pytest.fixture
def _clean_logs(db_session):
    """每个测试结束后清空调用日志，避免内存库数据跨测试残留"""
    yield
    db_session.query(LLMCallLog).delete()
    db_session.commit()


pytestmark = pytest.mark.usefixtures("_clean_logs")


def _add_log(db, user_id=1, model_name="deepseek-v4-flash-0731", p=1000, c=1000, status="success"):
    db.add(
        LLMCallLog(
            user_id=user_id,
            endpoint="/api/v1/chat",
            model_name=model_name,
            provider="custom",
            prompt="hi",
            response="hello",
            prompt_tokens=p,
            completion_tokens=c,
            total_tokens=p + c,
            latency_ms=100.0,
            estimated_cost_usd=0.0,
            status=status,
        )
    )
    db.commit()


class TestEstimateCostCny:
    def test_known_model_price(self):
        # deepseek-v4-flash-0731: 输入 3 元/M，输出 9 元/M
        # 1000 prompt + 1000 completion = (3 + 9) / 1000 = 0.012 元
        assert estimate_cost_cny("deepseek-v4-flash-0731", 1000, 1000) == pytest.approx(0.012)

    def test_unknown_model_falls_back_to_settings(self):
        # 未收录模型使用 settings 全局单价
        p = settings.LLM_INPUT_PRICE_PER_1M
        o = settings.LLM_OUTPUT_PRICE_PER_1M
        expected = (1000 * p + 2000 * o) / 1_000_000
        assert estimate_cost_cny("some-unknown-model", 1000, 2000) == pytest.approx(expected)


class TestGetSpentCny:
    def test_sums_success_only(self, db_session):
        _add_log(db_session, model_name="deepseek-v4-flash-0731", p=1_000_000, c=0)
        _add_log(db_session, model_name="deepseek-v4-flash-0731", p=0, c=1_000_000)
        _add_log(db_session, model_name="deepseek-v4-flash-0731", p=999_999, c=999_999, status="failed")
        # 失败调用不计费：3 + 9 = 12 元
        assert get_spent_cny(db_session, user_id=1) == pytest.approx(12.0)

    def test_isolated_per_user(self, db_session):
        _add_log(db_session, user_id=1, p=1_000_000, c=0)  # 3 元
        _add_log(db_session, user_id=2, p=1_000_000, c=0)  # 另一用户，3 元
        assert get_spent_cny(db_session, user_id=1) == pytest.approx(3.0)
        assert get_spent_cny(db_session, user_id=2) == pytest.approx(3.0)


class TestCheckBudget:
    def test_allows_under_budget(self, db_session, _restore_budget):
        settings.LLM_BUDGET_CNY = 45.0
        _add_log(db_session, p=100_000, c=100_000)  # 1.2 元
        status = check_budget(db_session, user_id=1)
        assert status.allowed is True
        assert status.spent_cny == pytest.approx(1.2)
        assert status.remaining_cny == pytest.approx(43.8)

    def test_rejects_at_red_line(self, db_session, _restore_budget):
        settings.LLM_BUDGET_CNY = 45.0
        _add_log(db_session, p=5_000_000, c=3_000_000)  # 5*3 + 3*9 = 42 元
        status = check_budget(db_session, user_id=1)
        assert status.allowed is True  # 42 < 45，仍放行

        _add_log(db_session, p=1_000_000, c=0)  # 再花 3 元 → 45 元，触线
        status = check_budget(db_session, user_id=1)
        assert status.allowed is False

    def test_disabled_when_budget_non_positive(self, db_session, _restore_budget):
        settings.LLM_BUDGET_CNY = 0
        _add_log(db_session, p=10_000_000, c=10_000_000)
        assert check_budget(db_session, user_id=1).allowed is True
        settings.LLM_BUDGET_CNY = -1
        assert check_budget(db_session, user_id=1).allowed is True

    def test_budget_status_remaining_never_negative(self):
        status = BudgetStatus(allowed=False, spent_cny=50.0, budget_cny=45.0)
        assert status.remaining_cny == 0.0
