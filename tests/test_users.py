def test_create_user(client):
    """
    测试用户注册功能
    """
    response = client.post(
        "/api/v1/users/",
        json={"username": "pytestuser", "email": "pytest@example.com", "password": "testpassword"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "pytest@example.com"
    assert data["username"] == "pytestuser"
    assert "id" in data
    # 确保密码不会在响应中返回
    assert "password" not in data
    assert "hashed_password" not in data


def test_change_password(client):
    email = "pwdchange@example.com"
    client.post(
        "/api/v1/users/",
        json={"username": "pwdchange", "email": email, "password": "oldpassword"},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "oldpassword"},
    )
    token = login_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    change_resp = client.put(
        "/api/v1/users/me/password",
        json={"old_password": "oldpassword", "new_password": "newpassword"},
        headers=headers,
    )
    assert change_resp.status_code == 200

    new_login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "newpassword"},
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

    old_login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "oldpassword"},
    )
    assert old_login.status_code == 401


def test_change_password_wrong_old_password(client):
    email = "wrongpwd@example.com"
    client.post(
        "/api/v1/users/",
        json={"username": "wrongpwd", "email": email, "password": "correctpwd"},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "correctpwd"},
    )
    token = login_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.put(
        "/api/v1/users/me/password",
        json={"old_password": "wrongold", "new_password": "newpassword"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 1008


def test_create_duplicate_user(client):
    response = client.post(
        "/api/v1/users/",
        json={
            "username": "pytestuser2",
            "email": "pytest@example.com",
            "password": "testpassword",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001
