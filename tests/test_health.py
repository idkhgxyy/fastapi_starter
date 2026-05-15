def test_health_check_returns_dependencies(client):
    response = client.get("/api/v1/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "dependencies" in data
    deps = data["dependencies"]
    assert "database" in deps
    assert "redis" in deps
    assert "ollama" in deps
    assert deps["database"]["status"] == "up"
    if response.status_code == 200:
        assert data["status"] == "ok"
    else:
        assert data["status"] == "degraded"


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]
