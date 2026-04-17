def test_create_user(client):
    """
    测试用户注册功能
    """
    response = client.post(
        "/api/users/",
        json={
            "username": "pytestuser",
            "email": "pytest@example.com",
            "password": "testpassword"
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "pytest@example.com"
    assert data["username"] == "pytestuser"
    assert "id" in data
    # 确保密码不会在响应中返回
    assert "password" not in data
    assert "hashed_password" not in data

def test_create_duplicate_user(client):
    """
    测试注册重复邮箱的用户应该失败
    """
    response = client.post(
        "/api/users/",
        json={
            "username": "pytestuser2",
            "email": "pytest@example.com",  # 相同的邮箱
            "password": "testpassword"
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001
