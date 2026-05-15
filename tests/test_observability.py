from time import perf_counter
from types import SimpleNamespace

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
