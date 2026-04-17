def test_health_check(client):
    """
    测试健康检查接口
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_root_endpoint(client):
    """
    测试根目录重定向信息
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]
