from time import perf_counter
from types import SimpleNamespace

import pytest

from app.models.llm_call_log import LLMCallLog
from app.services.llm_observability_service import (
    elapsed_ms,
    estimate_cost_usd,
    extract_usage,
    serialize_tool_calls,
    start_timer,
)


class TestTiming:
    def test_start_timer_returns_float(self):
        t = start_timer()
        assert isinstance(t, float)

    def test_elapsed_ms_returns_positive(self):
        t = start_timer()
        elapsed = elapsed_ms(t)
        assert elapsed >= 0

    def test_elapsed_ms_increases_over_time(self):
        t = perf_counter() - 1.0
        elapsed = elapsed_ms(t)
        assert elapsed >= 900


class TestCostEstimation:
    def test_zero_tokens_zero_cost(self):
        assert estimate_cost_usd(0, 0) == 0.0

    def test_cost_with_default_prices(self):
        cost = estimate_cost_usd(1000, 1000)
        assert cost == 0.0

    def test_cost_is_float(self):
        cost = estimate_cost_usd(500, 300)
        assert isinstance(cost, float)


class TestExtractUsage:
    def test_extract_usage_with_none_usage(self):
        response = SimpleNamespace(usage=None)
        assert extract_usage(response) == (0, 0, 0)

    def test_extract_usage_with_full_data(self):
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        response = SimpleNamespace(usage=usage)
        assert extract_usage(response) == (100, 50, 150)

    def test_extract_usage_with_partial_data(self):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=0, total_tokens=10)
        response = SimpleNamespace(usage=usage)
        assert extract_usage(response) == (10, 0, 10)


class TestSerializeToolCalls:
    def test_serialize_none_returns_none(self):
        assert serialize_tool_calls(None) is None

    def test_serialize_empty_list_returns_none(self):
        assert serialize_tool_calls([]) is None

    def test_serialize_single_tool_call(self):
        tool_call = SimpleNamespace(
            id="call_abc123",
            function=SimpleNamespace(
                name="get_current_weather",
                arguments='{"location": "Beijing"}',
            ),
        )
        result = serialize_tool_calls([tool_call])
        assert result is not None
        assert "get_current_weather" in result
        assert "Beijing" in result

    def test_serialize_multiple_tool_calls(self):
        tc1 = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="create_task", arguments='{"title": "A"}'),
        )
        tc2 = SimpleNamespace(
            id="call_2",
            function=SimpleNamespace(name="get_system_status", arguments="{}"),
        )
        result = serialize_tool_calls([tc1, tc2])
        assert result is not None
        assert "create_task" in result
        assert "get_system_status" in result


class TestLLMCallLogCostField:
    """
    回归：/observability/llm-calls 必须把人民币成本透给前端。

    曾经构造 LLMCallLogOut 时漏传 estimated_cost_cny，pydantic 用 schema 默认值 0.0
    兜住，于是数据库里明明有 ¥0.1356，日志明细表却整列显示 ¥0.0000。
    """

    def test_llm_calls_exposes_estimated_cost_cny(self, client, db_session):
        client.post(
            "/api/v1/users/",
            json={
                "username": "costviewer",
                "email": "costviewer@test.dev",
                "password": "testpassword",
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "costviewer@test.dev", "password": "testpassword"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        user_id = client.get("/api/v1/users/me", headers=headers).json()["id"]

        db_session.add(
            LLMCallLog(
                user_id=user_id,
                endpoint="/chat/",
                model_name="deepseek-v4.1-flash",
                provider="dashscope",
                prompt="hello",
                response="world",
                prompt_tokens=1000,
                completion_tokens=500,
                total_tokens=1500,
                latency_ms=120.0,
                estimated_cost_usd=0.0,
                estimated_cost_cny=0.1234,
                status="success",
            )
        )
        db_session.commit()

        resp = client.get("/api/v1/observability/llm-calls?limit=10", headers=headers)
        assert resp.status_code == 200
        mine = [r for r in resp.json() if r["model_name"] == "deepseek-v4.1-flash"]
        assert mine, "刚写入的调用日志应当出现在明细列表里"
        assert mine[0]["estimated_cost_cny"] == pytest.approx(0.1234)
        assert mine[0]["estimated_cost_usd"] == pytest.approx(0.0)
