"""
LLM 本地工具函数单元测试 (get_current_weather, get_system_status)
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.services import llm_service
from app.services.llm_service import get_current_weather, get_system_status


class TestWeatherTool:
    def test_known_city_beijing(self):
        result = get_current_weather("北京")
        assert "晴天" in result
        assert "25°C" in result

    def test_known_city_shanghai(self):
        result = get_current_weather("上海")
        assert "多云" in result
        assert "28°C" in result

    def test_known_city_guangzhou(self):
        result = get_current_weather("广州")
        assert "小雨" in result
        assert "26°C" in result

    def test_unknown_city_returns_default(self):
        result = get_current_weather("火星")
        assert "未知" in result
        assert "20°C" in result

    def test_empty_location(self):
        result = get_current_weather("")
        assert "未知" in result


class TestSystemStatusTool:
    def test_returns_cpu_info(self):
        result = get_system_status()
        assert "CPU 使用率" in result

    def test_returns_memory_info(self):
        result = get_system_status()
        assert "内存使用率" in result

    def test_returns_disk_info(self):
        result = get_system_status()
        assert "磁盘使用率" in result

    def test_returns_non_empty_string(self):
        result = get_system_status()
        assert isinstance(result, str)
        assert len(result) > 0


class TestCalculateTool:
    def test_basic_arithmetic(self):
        from app.services.llm_service import calculate

        result = calculate("2 + 3 * 4")
        assert "14" in result

    def test_simple_addition(self):
        from app.services.llm_service import calculate

        result = calculate("1 + 1")
        assert "2" in result

    def test_round_function(self):
        from app.services.llm_service import calculate

        result = calculate("round(3.14159, 2)")
        assert "3.14" in result

    def test_pow_function(self):
        from app.services.llm_service import calculate

        result = calculate("pow(2, 10)")
        assert "1024" in result

    def test_invalid_expression(self):
        from app.services.llm_service import calculate

        result = calculate("1 / 0")
        assert "计算失败" in result

    def test_safety_no_builtins(self):
        from app.services.llm_service import calculate

        result = calculate("__import__('os').system('ls')")
        assert "计算失败" in result


class _FakeDelta:
    def __init__(self, *, content=None, reasoning_content=None, tool_calls=None):
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls


class _FakeStream:
    """可迭代的假流，模拟 OpenAI 兼容协议的 chunk 序列。"""

    def __init__(self, deltas, usage=None):
        self._chunks = [
            SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=delta)]) for delta in deltas
        ]
        if usage is not None:
            self._chunks.append(SimpleNamespace(usage=usage, choices=[]))
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)

    async def close(self):
        self.closed = True


def _collect_stream(message: str):
    async def drain():
        chunks = []
        async for item in llm_service.generate_chat_reply_stream(
            message=message, db=None, current_user_id=None, session_id=None
        ):
            chunks.append(item)
        return chunks

    return asyncio.run(drain())


class TestStreamToolHandoff:
    """流式探测到工具调用时，必须转交非流式工具链，结果仍以 SSE 返回。"""

    def _fake_info(self, stream):
        async def fake_create(**kwargs):
            assert kwargs.get("stream") is True
            return stream

        return SimpleNamespace(
            model_name="fake-model",
            client=SimpleNamespace(
                api_key="fake-key",
                chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)),
            ),
        )

    def test_tool_call_in_stream_delegates_to_non_streaming(self):
        stream = _FakeStream([_FakeDelta(tool_calls=[SimpleNamespace(id="call_1")])])
        info = self._fake_info(stream)
        called = {}

        async def fake_generate_chat_reply(message, db=None, current_user_id=None, session_id=None):
            called["message"] = message
            return "工具已执行：已创建任务"

        with (
            patch.object(llm_service, "get_llm_client", lambda user=None: info),
            patch.object(llm_service, "_build_fallback_info", lambda: None),
            patch.object(llm_service, "generate_chat_reply", fake_generate_chat_reply),
        ):
            text = "".join(_collect_stream("帮我建一个复习任务"))

        assert "工具已执行：已创建任务" in text
        assert text.rstrip().endswith("data: [DONE]")
        assert called["message"] == "帮我建一个复习任务"
        assert stream.closed is True

    def test_plain_content_stream_does_not_delegate(self):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        stream = _FakeStream(
            [_FakeDelta(content="你"), _FakeDelta(content="好")],
            usage=usage,
        )
        info = self._fake_info(stream)
        delegate_calls = []

        async def fake_generate_chat_reply(*args, **kwargs):
            delegate_calls.append(kwargs)
            return "不应被调用"

        with (
            patch.object(llm_service, "get_llm_client", lambda user=None: info),
            patch.object(llm_service, "_build_fallback_info", lambda: None),
            patch.object(llm_service, "generate_chat_reply", fake_generate_chat_reply),
        ):
            text = "".join(_collect_stream("你好"))

        assert '"content": "你"' in text
        assert '"content": "好"' in text
        assert "不应被调用" not in text
        assert delegate_calls == []
        assert stream.closed is False

    def test_done_is_always_the_last_chunk(self):
        """[DONE] 必须先于收尾工作发出吗？不——必须最后发。

        客户端收到 [DONE] 立即断开、Starlette 随之取消生成器；若把记账/缓存等
        await 型收尾放在 DONE 之后，它们会在等网络时被取消（线上曾因此缓存恒空）。
        """
        stream = _FakeStream([_FakeDelta(content="好")])
        info = self._fake_info(stream)

        with (
            patch.object(llm_service, "get_llm_client", lambda user=None: info),
            patch.object(llm_service, "_build_fallback_info", lambda: None),
        ):
            chunks = _collect_stream("你好")

        assert chunks[-1] == "data: [DONE]\n\n"
        assert all("[DONE]" not in chunk for chunk in chunks[:-1])
