"""云端→本地 Ollama 降级链单元测试"""

import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import llm_service
from app.services.cost_guard import BudgetStatus


def _make_usage(prompt=100, completion=50):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion)


def _make_response(content="本地模型的回答"):
    message = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=_make_usage())


class FakeCompletions:
    """按 kwargs 里的 tools 参数区分 Round1/Round2，可配置抛错"""

    def __init__(self, response=None, error: Exception = None):
        self.response = response or _make_response()
        self.error = error

    async def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error: Exception = None):
        self.api_key = "fake-key"
        self.chat = SimpleNamespace(completions=FakeCompletions(response, error))


def _info(client):
    return llm_service.LLMClientInfo(client=client, model_name="fake-model")


@pytest.fixture
def _restore_mock():
    old = settings.LLM_MOCK
    old_ollama = settings.OLLAMA_ENABLED
    yield
    settings.LLM_MOCK = old
    settings.OLLAMA_ENABLED = old_ollama


class TestBuildFallbackInfo:
    def test_returns_none_in_mock_mode(self, _restore_mock):
        settings.LLM_MOCK = True
        assert llm_service._build_fallback_info() is None

    def test_returns_none_when_ollama_disabled(self, _restore_mock):
        # 轻量部署模式：不部署 Ollama，降级链关闭
        settings.LLM_MOCK = False
        settings.OLLAMA_ENABLED = False
        assert llm_service._build_fallback_info() is None

    def test_returns_ollama_info(self, db_session, _restore_mock):
        settings.LLM_MOCK = False
        settings.OLLAMA_ENABLED = True
        info = llm_service._build_fallback_info()
        assert info is not None
        assert info.model_name == settings.OLLAMA_FALLBACK_MODEL


class TestFallbackChain:
    def test_cloud_failure_falls_back_to_local(self, monkeypatch):
        cloud = _info(FakeClient(error=RuntimeError("connection refused")))
        local = _info(FakeClient(response=_make_response("来自本地的回答")))
        monkeypatch.setattr(llm_service, "get_llm_client", lambda user: cloud)
        monkeypatch.setattr(llm_service, "_build_fallback_info", lambda: local)

        reply = asyncio.run(llm_service.generate_chat_reply("你好"))
        assert "本地模型" in reply
        assert "来自本地的回答" in reply

    def test_budget_blocked_uses_local_only(self, db_session, monkeypatch):
        cloud = _info(FakeClient(response=_make_response("云端不该被调用")))
        local = _info(FakeClient(response=_make_response("预算触顶后的本地回答")))

        def _blocked(db, user_id):
            return BudgetStatus(allowed=False, spent_cny=50.0, budget_cny=45.0)

        monkeypatch.setattr(llm_service, "check_budget", _blocked)
        monkeypatch.setattr(llm_service, "get_llm_client", lambda user: cloud)
        monkeypatch.setattr(llm_service, "_build_fallback_info", lambda: local)

        reply = asyncio.run(llm_service.generate_chat_reply("你好", db=db_session))
        assert "已达到云端预算" in reply
        assert "预算触顶后的本地回答" in reply

    def test_budget_blocked_without_fallback_rejects(self, db_session, monkeypatch):
        cloud = _info(FakeClient(response=_make_response("云端不该被调用")))

        def _blocked(db, user_id):
            return BudgetStatus(allowed=False, spent_cny=50.0, budget_cny=45.0)

        monkeypatch.setattr(llm_service, "check_budget", _blocked)
        monkeypatch.setattr(llm_service, "get_llm_client", lambda user: cloud)
        monkeypatch.setattr(llm_service, "_build_fallback_info", lambda: None)

        reply = asyncio.run(llm_service.generate_chat_reply("你好", db=db_session))
        assert "成本熔断" in reply

    def test_all_candidates_fail_returns_error(self, monkeypatch):
        cloud = _info(FakeClient(error=RuntimeError("cloud down")))
        local = _info(FakeClient(error=RuntimeError("ollama down")))
        monkeypatch.setattr(llm_service, "get_llm_client", lambda user: cloud)
        monkeypatch.setattr(llm_service, "_build_fallback_info", lambda: local)

        reply = asyncio.run(llm_service.generate_chat_reply("你好"))
        assert "模型调用失败" in reply

    def test_cloud_success_no_fallback_note(self, monkeypatch):
        cloud = _info(FakeClient(response=_make_response("云端正常回答")))
        monkeypatch.setattr(llm_service, "get_llm_client", lambda user: cloud)

        def _ok(db, user_id):
            return BudgetStatus(allowed=True, spent_cny=0.0, budget_cny=45.0)

        monkeypatch.setattr(llm_service, "check_budget", _ok)

        reply = asyncio.run(llm_service.generate_chat_reply("你好"))
        assert reply == "云端正常回答"
