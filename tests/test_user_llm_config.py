import pytest
from httpx import AsyncClient

def test_user_llm_config(client):
    # 1. Create a user
    client.post(
        "/api/users/",
        json={
            "username": "llm_user",
            "email": "llm@example.com",
            "password": "password123"
        },
    )
    
    # 2. Login
    login_resp = client.post(
        "/api/auth/login",
        data={
            "username": "llm@example.com",
            "password": "password123"
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Check initial config
    me_resp = client.get("/api/users/me", headers=headers)
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["has_custom_llm_key"] is False
    assert data["llm_provider"] is None
    
    # 4. Update config
    update_resp = client.put(
        "/api/users/me/llm-config",
        headers=headers,
        json={
            "llm_provider": "custom_openai",
            "llm_base_url": "https://api.openai.com/v1",
            "llm_model_name": "gpt-4o",
            "llm_api_key": "sk-123456789"
        }
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["llm_provider"] == "custom_openai"
    assert updated_data["llm_base_url"] == "https://api.openai.com/v1"
    assert updated_data["llm_model_name"] == "gpt-4o"
    assert updated_data["has_custom_llm_key"] is True
    assert "llm_api_key" not in updated_data  # Should not expose raw key
    assert "llm_api_key_encrypted" not in updated_data # Should not expose encrypted key either
