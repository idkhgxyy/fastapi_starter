from fastapi import status

from app.utils.errors import AppException


class TestAppException:
    def test_create_exception_with_defaults(self):
        exc = AppException(code=1001, msg="test error")
        assert exc.code == 1001
        assert exc.msg == "test error"
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.data is None

    def test_create_exception_with_custom_status(self):
        exc = AppException(code=2001, msg="not found", status_code=status.HTTP_404_NOT_FOUND)
        assert exc.status_code == status.HTTP_404_NOT_FOUND

    def test_create_exception_with_data(self):
        exc = AppException(code=3001, msg="validation error", data={"field": "email"})
        assert exc.data == {"field": "email"}


class TestErrorResponseFormat:
    def test_login_with_wrong_credentials_returns_error_format(self, client):
        client.post(
            "/api/v1/users/",
            json={
                "username": "errorfmt",
                "email": "errorfmt@example.com",
                "password": "pass123",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "errorfmt@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        json_data = response.json()
        assert "code" in json_data
        assert "msg" in json_data
        assert json_data["code"] == 1005

    def test_unauthenticated_request_returns_401(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
        json_data = response.json()
        # HTTPException 已被全局处理器转换为统一格式
        assert "code" in json_data
        assert "msg" in json_data
        assert json_data["code"] == 1008

    def test_duplicate_registration_returns_error_format(self, client):
        client.post(
            "/api/v1/users/",
            json={
                "username": "dup1",
                "email": "dup@example.com",
                "password": "pass123",
            },
        )
        response = client.post(
            "/api/v1/users/",
            json={
                "username": "dup2",
                "email": "dup@example.com",
                "password": "pass123",
            },
        )
        assert response.status_code == 400
        json_data = response.json()
        assert json_data["code"] == 1001
