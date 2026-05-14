"""
任务 CRUD 端到端测试 (通过 API 接口)
"""

def _create_user_and_get_token(client, suffix: str) -> str:
    email = f"task-{suffix}@example.com"
    password = "password123"
    client.post(
        "/api/users/",
        json={
            "username": f"taskuser-{suffix}",
            "email": email,
            "password": password,
        },
    )
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestTaskCreate:
    def test_create_task_success(self, client):
        token = _create_user_and_get_token(client, "create")
        response = client.post(
            "/api/tasks/",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "学习 FastAPI", "description": "阅读文档并写demo"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "学习 FastAPI"
        assert data["description"] == "阅读文档并写demo"
        assert data["status"] == "pending"
        assert "id" in data
        assert "owner_id" in data

    def test_create_task_without_auth_fails(self, client):
        response = client.post(
            "/api/tasks/",
            json={"title": "unauthorized task"},
        )
        assert response.status_code == 401

    def test_create_task_missing_title_fails(self, client):
        token = _create_user_and_get_token(client, "no-title")
        response = client.post(
            "/api/tasks/",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": "no title"},
        )
        assert response.status_code == 422


class TestTaskList:
    def test_list_tasks_returns_user_tasks(self, client):
        token = _create_user_and_get_token(client, "list")
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/api/tasks/", headers=headers, json={"title": "任务A"})
        client.post("/api/tasks/", headers=headers, json={"title": "任务B"})
        response = client.get("/api/tasks/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        titles = {item["title"] for item in data}
        assert titles == {"任务A", "任务B"}

    def test_list_tasks_user_isolation(self, client):
        token_a = _create_user_and_get_token(client, "isolate-a")
        token_b = _create_user_and_get_token(client, "isolate-b")
        client.post(
            "/api/tasks/",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"title": "用户A的任务"},
        )
        client.post(
            "/api/tasks/",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"title": "用户B的任务"},
        )
        resp_a = client.get("/api/tasks/", headers={"Authorization": f"Bearer {token_a}"})
        resp_b = client.get("/api/tasks/", headers={"Authorization": f"Bearer {token_b}"})
        assert len(resp_a.json()) == 1
        assert resp_a.json()[0]["title"] == "用户A的任务"
        assert len(resp_b.json()) == 1
        assert resp_b.json()[0]["title"] == "用户B的任务"

    def test_list_tasks_empty(self, client):
        token = _create_user_and_get_token(client, "empty")
        response = client.get("/api/tasks/", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == []


class TestTaskGet:
    def test_get_task_by_id(self, client):
        token = _create_user_and_get_token(client, "get")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post(
            "/api/tasks/", headers=headers,
            json={"title": "获取测试"},
        )
        task_id = created.json()["id"]
        response = client.get(f"/api/tasks/{task_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["title"] == "获取测试"

    def test_get_task_not_found(self, client):
        token = _create_user_and_get_token(client, "nf")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/tasks/99999", headers=headers)
        assert response.status_code == 404

    def test_get_task_other_user_forbidden(self, client):
        token_a = _create_user_and_get_token(client, "other-a")
        token_b = _create_user_and_get_token(client, "other-b")
        created = client.post(
            "/api/tasks/",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"title": "私密任务"},
        )
        task_id = created.json()["id"]
        response = client.get(
            f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404


class TestTaskUpdate:
    def test_update_task_title(self, client):
        token = _create_user_and_get_token(client, "upd-title")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/tasks/", headers=headers, json={"title": "原始标题"})
        task_id = created.json()["id"]
        response = client.put(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"title": "新标题"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "新标题"

    def test_update_task_status(self, client):
        token = _create_user_and_get_token(client, "upd-status")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/tasks/", headers=headers, json={"title": "待办"})
        task_id = created.json()["id"]
        response = client.put(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"status": "completed"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_update_task_partial(self, client):
        token = _create_user_and_get_token(client, "upd-partial")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post(
            "/api/tasks/",
            headers=headers,
            json={"title": "部分更新", "description": "原始描述", "status": "pending"},
        )
        task_id = created.json()["id"]
        response = client.put(
            f"/api/tasks/{task_id}",
            headers=headers,
            json={"description": "新描述"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "部分更新"
        assert data["description"] == "新描述"
        assert data["status"] == "pending"


class TestTaskDelete:
    def test_delete_task(self, client):
        token = _create_user_and_get_token(client, "delete")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/tasks/", headers=headers, json={"title": "待删除"})
        task_id = created.json()["id"]
        response = client.delete(f"/api/tasks/{task_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["title"] == "待删除"
        get_resp = client.get(f"/api/tasks/{task_id}", headers=headers)
        assert get_resp.status_code == 404

    def test_delete_task_not_found(self, client):
        token = _create_user_and_get_token(client, "del-nf")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.delete("/api/tasks/99999", headers=headers)
        assert response.status_code == 404
