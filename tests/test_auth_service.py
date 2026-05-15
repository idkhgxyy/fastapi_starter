"""
Auth 服务层单元测试
"""

from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.services.user_service import UserService


class TestAuthService:
    def test_authenticate_valid_user(self, db_session):
        user_in = UserCreate(
            username="auth_test",
            email="auth_test@example.com",
            password="valid_password",
        )
        created = UserService.create_user(db_session, user_in)
        user = AuthService.authenticate_user(db_session, "auth_test@example.com", "valid_password")
        assert user is not None
        assert user.id == created.id

    def test_authenticate_wrong_password(self, db_session):
        UserService.create_user(
            db_session,
            UserCreate(username="wrongpw", email="wrongpw@example.com", password="correct1"),
        )
        user = AuthService.authenticate_user(db_session, "wrongpw@example.com", "wrong_password")
        assert user is None

    def test_authenticate_nonexistent_email(self, db_session):
        user = AuthService.authenticate_user(db_session, "noone@example.com", "any_password")
        assert user is None
