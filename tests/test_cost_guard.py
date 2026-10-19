"""成本熔断（cost_guard）单元测试"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models.llm_call_log import LLMCallLog
from app.models.user import User
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
    def test_known_model_price(self, db_session):
        # deepseek-v4-flash-0731: 输入 3 元/M，输出 9 元/M（未种子化时回退全局配置，数值相同）
        # 1000 prompt + 1000 completion = (3 + 9) / 1000 = 0.012 元
        assert estimate_cost_cny(
            db_session, "deepseek-v4-flash-0731", 1000, 1000
        ) == pytest.approx(0.012)

    def test_unknown_model_falls_back_to_settings(self, db_session):
        # 未收录模型使用 settings 全局单价
        p = settings.LLM_INPUT_PRICE_PER_1M
        o = settings.LLM_OUTPUT_PRICE_PER_1M
        expected = (1000 * p + 2000 * o) / 1_000_000
        assert estimate_cost_cny(db_session, "some-unknown-model", 1000, 2000) == pytest.approx(expected)


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


def _add_log_at(db, user_id=1, p=0, c=0, created_at=None, model_name="deepseek-v4.1-flash"):
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
            status="success",
            created_at=created_at,
        )
    )
    db.commit()


class TestMonthlyBudget:
    def test_only_counts_current_period(self, db_session, _restore_budget, _clean_logs):
        settings.LLM_BUDGET_CNY = 45.0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # 上月最后一刻：本月1日零点的前一小时
        last_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(
            hours=1
        )
        # 上月花了 112.5 元，本月花了 4.5 元（测试库定价表未种子化，回退全局单价 3/9）
        _add_log_at(db_session, p=0, c=12_500_000, created_at=last_month)  # 12.5M×9 = 112.5 元
        _add_log_at(db_session, p=1_000_000, c=0, created_at=now)  # 1M×3 = 3 元
        _add_log_at(db_session, p=500_000, c=0, created_at=now)  # 0.5M×3 = 1.5 元

        status = check_budget(db_session, user_id=1)
        assert status.spent_cny == pytest.approx(4.5)  # 只算本月
        assert status.allowed is True
        assert status.period == "monthly"
        assert status.period_start is not None
        assert status.period_start.day == 1

    def test_personal_budget_overrides_global(self, db_session, _restore_budget, _clean_logs):
        settings.LLM_BUDGET_CNY = 45.0
        db_session.add(
            User(
                username="budgeter",
                email="budgeter@test.dev",
                hashed_password="x",
                budget_cny=1.0,
                budget_period="monthly",
            )
        )
        db_session.commit()
        uid = db_session.query(User).filter_by(username="budgeter").first().id

        _add_log_at(db_session, user_id=uid, p=600_000, c=0)  # 1.2 元 > 个人预算 1 元
        status = check_budget(db_session, user_id=uid)
        assert status.allowed is False  # 全局 45 元会放行，个人 1 元拦住
        assert status.budget_cny == pytest.approx(1.0)

    def test_null_personal_budget_falls_back_global(self, db_session, _restore_budget, _clean_logs):
        settings.LLM_BUDGET_CNY = 45.0
        db_session.add(
            User(
                username="nobudget",
                email="nobudget@test.dev",
                hashed_password="x",
                budget_cny=None,
            )
        )
        db_session.commit()
        uid = db_session.query(User).filter_by(username="nobudget").first().id

        _add_log_at(db_session, user_id=uid, p=600_000, c=0)  # 1.2 元
        status = check_budget(db_session, user_id=uid)
        assert status.allowed is True
        assert status.budget_cny == pytest.approx(45.0)


class TestBudgetAPI:
    def test_get_and_put_budget_roundtrip(self, client, _restore_budget):
        settings.LLM_BUDGET_CNY = 45.0
        client.post(
            "/api/v1/users/",
            json={"username": "api_budgeter", "email": "api_budgeter@test.dev", "password": "testpassword"},
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "api_budgeter@test.dev", "password": "testpassword"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 初始：无个人预算，回退全局
        resp = client.get("/api/v1/users/me/budget", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_personal_budget"] is False
        assert data["budget_cny"] == pytest.approx(45.0)

        # 设置个人预算
        resp = client.put(
            "/api/v1/users/me/budget", json={"budget_cny": 10.0}, headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_personal_budget"] is True
        assert data["budget_cny"] == pytest.approx(10.0)

        # 置 null 回退全局
        resp = client.put(
            "/api/v1/users/me/budget", json={"budget_cny": None}, headers=headers
        )
        assert resp.json()["has_personal_budget"] is False
        assert resp.json()["budget_cny"] == pytest.approx(45.0)
