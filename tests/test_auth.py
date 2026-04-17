def test_login_success(client):
    """
    测试登录成功获取 Token
    注意：此测试依赖于 test_users.py 中先创建好的 pytest@example.com 用户。
    由于 pytest 默认按字母顺序执行文件，test_users.py 会在 test_auth.py 之后执行，
    所以我们在 auth 测试里先确保创建一个用户。
    """
    # 1. 准备测试数据：创建一个用户
    client.post(
        "/api/users/",
        json={
            "username": "authuser",
            "email": "auth@example.com",
            "password": "authpassword"
        },
    )

    # 2. 测试登录
    response = client.post(
        "/api/auth/login",
        data={
            "username": "auth@example.com",
            "password": "authpassword"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(client):
    """
    测试错误密码登录
    """
    response = client.post(
        "/api/auth/login",
        data={
            "username": "auth@example.com",
            "password": "wrongpassword"
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == 1005

def test_access_protected_route_without_token(client):
    """
    测试不带 Token 访问受保护接口
    """
    response = client.get("/api/users/me")
    assert response.status_code == 401
