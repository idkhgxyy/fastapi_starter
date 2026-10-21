"""目标型 Agent 任务：接口、隔离、执行流水线与导出测试。"""

import asyncio
from types import SimpleNamespace

import pytest

from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.document import DOCUMENT_STATUS_READY, Document
from app.models.llm_call_log import LLMCallLog
from app.services import agent_task_service


def _create_user_and_login(client, suffix: str) -> tuple[str, int]:
    email = f"agent-{suffix}@example.com"
    password = "password123"
    client.post(
        "/api/v1/users/",
        json={"username": f"agentuser-{suffix}", "email": email, "password": password},
    )
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    user_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()[
        "id"
    ]
    return token, user_id


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def no_queue(monkeypatch):
    """拦截 Celery 投递，避免测试真的去连 broker。"""
    enqueued: list[int] = []

    class DummyTask:
        id = "dummy-task-id"

    monkeypatch.setattr(
        "app.api.routers.agent_tasks.run_agent_task_task.delay",
        lambda task_id: (enqueued.append(task_id), DummyTask())[1],
    )
    return enqueued


@pytest.fixture
def fake_llm(monkeypatch):
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            prompt = kwargs["messages"][1]["content"]
            if "二级标题" in prompt:
                content = "背景与目标\n关键材料\n分析与建议"
            else:
                content = "这是依据材料撰写的小节正文。"
            usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=usage,
            )

    info = SimpleNamespace(
        model_name="fake-model",
        client=SimpleNamespace(
            api_key="fake-key",
            chat=SimpleNamespace(completions=FakeCompletions()),
        ),
    )
    monkeypatch.setattr(agent_task_service, "get_llm_client", lambda user=None: info)
    return calls


def _add_document(db, *, owner, filename="课设要求.docx", summary="题目列表与要求"):
    document = Document(
        owner_id=owner,
        filename=filename,
        file_type="docx",
        content="材料正文",
        status=DOCUMENT_STATUS_READY,
        chunks_count=1,
        summary=summary,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


class TestCreateTask:
    def test_auto_scope(self, client, no_queue):
        token, _ = _create_user_and_login(client, "auto")
        response = client.post(
            "/api/v1/agent-tasks/",
            headers=_headers(token),
            json={"goal": "帮我基于课设资料写一份选题分析", "scope_mode": "auto"},
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "pending"
        assert payload["scope_document_ids"] is None
        assert no_queue == [payload["id"]]

    def test_selected_scope(self, client, db_session, no_queue):
        token, user_id = _create_user_and_login(client, "selected")
        document = _add_document(db_session, owner=user_id)
        response = client.post(
            "/api/v1/agent-tasks/",
            headers=_headers(token),
            json={
                "goal": "只根据这篇文档写摘要",
                "scope_mode": "selected",
                "document_ids": [document.id],
            },
        )
        assert response.status_code == 202
        assert response.json()["scope_document_ids"] == [document.id]

    def test_selected_requires_documents(self, client, no_queue):
        token, _ = _create_user_and_login(client, "empty-scope")
        response = client.post(
            "/api/v1/agent-tasks/",
            headers=_headers(token),
            json={"goal": "写点东西", "scope_mode": "selected", "document_ids": []},
        )
        assert response.status_code == 400

    def test_rejects_foreign_document(self, client, db_session, no_queue):
        token_a, _ = _create_user_and_login(client, "foreign-a")
        _, user_b = _create_user_and_login(client, "foreign-b")
        foreign_doc = _add_document(db_session, owner=user_b, filename="别人的.pdf")

        response = client.post(
            "/api/v1/agent-tasks/",
            headers=_headers(token_a),
            json={
                "goal": "偷看别人的资料",
                "scope_mode": "selected",
                "document_ids": [foreign_doc.id],
            },
        )
        assert response.status_code == 400

    def test_budget_blocked(self, client, db_session, no_queue):
        from app.core.config import settings

        old_budget = settings.LLM_BUDGET_CNY
        settings.LLM_BUDGET_CNY = 0.0001
        try:
            token, user_id = _create_user_and_login(client, "budget")
            db_session.add(
                LLMCallLog(
                    user_id=user_id,
                    endpoint="/api/v1/chat",
                    model_name="deepseek-v4.1-flash",
                    provider="custom",
                    prompt="hi",
                    response="x",
                    prompt_tokens=1_000_000,
                    completion_tokens=0,
                    total_tokens=1_000_000,
                    latency_ms=1.0,
                    estimated_cost_usd=0.0,
                    status="success",
                )
            )
            db_session.commit()

            response = client.post(
                "/api/v1/agent-tasks/",
                headers=_headers(token),
                json={"goal": "预算已经超了还要写报告"},
            )
            assert response.status_code == 402
            assert "成本熔断" in str(response.json())
        finally:
            settings.LLM_BUDGET_CNY = old_budget


class TestIsolationAndCrud:
    def test_other_user_cannot_read_or_delete(self, client, no_queue):
        token_a, _ = _create_user_and_login(client, "iso-a")
        token_b, _ = _create_user_and_login(client, "iso-b")
        task_id = client.post(
            "/api/v1/agent-tasks/", headers=_headers(token_a), json={"goal": "我的任务"}
        ).json()["id"]

        assert (
            client.get(f"/api/v1/agent-tasks/{task_id}", headers=_headers(token_b)).status_code
            == 404
        )
        assert (
            client.delete(f"/api/v1/agent-tasks/{task_id}", headers=_headers(token_b)).status_code
            == 404
        )
        assert client.get("/api/v1/agent-tasks/", headers=_headers(token_b)).json() == []

    def test_delete_cascades_steps(self, client, db_session, no_queue):
        token, _ = _create_user_and_login(client, "cascade")
        task_id = client.post(
            "/api/v1/agent-tasks/", headers=_headers(token), json={"goal": "待删除任务"}
        ).json()["id"]
        db_session.add(AgentTaskStep(task_id=task_id, seq=1, name="retrieve", status="succeeded"))
        db_session.commit()

        assert (
            client.delete(f"/api/v1/agent-tasks/{task_id}", headers=_headers(token)).status_code
            == 200
        )
        assert db_session.query(AgentTaskStep).filter_by(task_id=task_id).count() == 0


class TestExecution:
    def test_generates_report_and_steps(self, client, db_session, no_queue, fake_llm):
        token, user_id = _create_user_and_login(client, "run")
        _add_document(db_session, owner=user_id)
        task_id = client.post(
            "/api/v1/agent-tasks/",
            headers=_headers(token),
            json={"goal": "写一份课设选题分析"},
        ).json()["id"]

        asyncio.run(agent_task_service.run_task(db_session, task_id))

        task = db_session.get(AgentTask, task_id)
        assert task.status == "succeeded"
        assert "## 背景与目标" in task.result_markdown
        assert "## 参考材料" in task.result_markdown
        assert task.prompt_tokens > 0 and task.cost_cny > 0

        step_names = [step.name for step in task.steps]
        assert step_names[0] == "retrieve"
        assert step_names[1] == "outline"
        assert step_names.count("write") == 3
        assert step_names[-1] == "finalize"

        log_count = (
            db_session.query(LLMCallLog).filter_by(user_id=user_id, endpoint="/agent-task").count()
        )
        assert log_count == 4  # 大纲 1 + 正文 3

    def test_no_documents_fails_with_message(self, client, db_session, no_queue, fake_llm):
        token, _ = _create_user_and_login(client, "no-docs")
        task_id = client.post(
            "/api/v1/agent-tasks/", headers=_headers(token), json={"goal": "没有资料也想写"}
        ).json()["id"]

        asyncio.run(agent_task_service.run_task(db_session, task_id))

        task = db_session.get(AgentTask, task_id)
        assert task.status == "failed"
        assert "没有可用的已就绪文档" in task.error_message

    def test_retry_only_failed(self, client, db_session, no_queue):
        token, _ = _create_user_and_login(client, "retry")
        task_id = client.post(
            "/api/v1/agent-tasks/", headers=_headers(token), json={"goal": "待重试"}
        ).json()["id"]
        task = db_session.get(AgentTask, task_id)
        task.status = "failed"
        task.error_message = "boom"
        db_session.commit()

        no_queue.clear()
        response = client.post(f"/api/v1/agent-tasks/{task_id}/retry", headers=_headers(token))
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        assert no_queue == [task_id]


class TestExport:
    def test_export_returns_markdown(self, client, db_session, no_queue):
        token, _ = _create_user_and_login(client, "export")
        task_id = client.post(
            "/api/v1/agent-tasks/", headers=_headers(token), json={"goal": "导出测试"}
        ).json()["id"]
        task = db_session.get(AgentTask, task_id)
        task.result_markdown = "# 成果\n\n正文"
        db_session.commit()

        response = client.get(f"/api/v1/agent-tasks/{task_id}/export", headers=_headers(token))
        assert response.status_code == 200
        assert response.text == "# 成果\n\n正文"
        assert "text/markdown" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]

    def test_export_without_result_returns_400(self, client, no_queue):
        token, _ = _create_user_and_login(client, "export-empty")
        task_id = client.post(
            "/api/v1/agent-tasks/", headers=_headers(token), json={"goal": "还没跑"}
        ).json()["id"]
        response = client.get(f"/api/v1/agent-tasks/{task_id}/export", headers=_headers(token))
        assert response.status_code == 400
