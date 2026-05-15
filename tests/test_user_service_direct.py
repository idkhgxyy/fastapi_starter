"""
User 服务层直接调用单元测试
"""

from app.schemas.user import UserCreate, UserLLMConfigUpdate
from app.services.user_service import UserService


class TestUserService:
    def test_create_and_get_user(self, db_session):
        user_in = UserCreate(
            username="svc_user",
            email="svc_user@example.com",
            password="mypassword",
        )
        created = UserService.create_user(db_session, user_in)
        assert created.username == "svc_user"
        assert created.email == "svc_user@example.com"
        assert created.is_active is True
        fetched = UserService.get_user(db_session, created.id)
        assert fetched.id == created.id

    def test_create_duplicate_email_raises(self, db_session):
        user_in = UserCreate(
            username="dup_a",
            email="dup_svc@example.com",
            password="password123",
        )
        UserService.create_user(db_session, user_in)
        from app.utils.errors import AppException

        try:
            UserService.create_user(
                db_session,
                UserCreate(username="dup_b", email="dup_svc@example.com", password="password123"),
            )
            assert False, "should have raised"
        except AppException as e:
            assert e.code == 1001

    def test_list_users(self, db_session):
        initial_count = len(UserService.list_users(db_session))
        UserService.create_user(
            db_session,
            UserCreate(username="list_a", email="list_a@example.com", password="password123"),
        )
        UserService.create_user(
            db_session,
            UserCreate(username="list_b", email="list_b@example.com", password="password123"),
        )
        assert len(UserService.list_users(db_session)) == initial_count + 2

    def test_delete_user(self, db_session):
        created = UserService.create_user(
            db_session,
            UserCreate(username="del_me", email="del_me@example.com", password="password123"),
        )
        deleted = UserService.delete_user(db_session, created.id)
        assert deleted.id == created.id

    def test_get_user_not_found_raises(self, db_session):
        from app.utils.errors import AppException

        try:
            UserService.get_user(db_session, 99999)
            assert False, "should have raised"
        except AppException as e:
            assert e.code == 1002

    def test_update_llm_config(self, db_session):
        created = UserService.create_user(
            db_session,
            UserCreate(username="llm_cfg", email="llm_cfg@example.com", password="password123"),
        )
        config = UserLLMConfigUpdate(
            llm_provider="openai",
            llm_base_url="https://api.openai.com/v1",
            llm_model_name="gpt-4o",
            llm_api_key="sk-test-key",
        )
        updated = UserService.update_llm_config(db_session, created.id, config)
        assert updated.llm_provider == "openai"
        assert updated.llm_base_url == "https://api.openai.com/v1"
        assert updated.llm_model_name == "gpt-4o"
        assert updated.has_custom_llm_key is True

    def test_update_llm_config_clear_key(self, db_session):
        created = UserService.create_user(
            db_session,
            UserCreate(username="clear_llm", email="clear_llm@example.com", password="password123"),
        )
        config_set = UserLLMConfigUpdate(
            llm_provider="openai",
            llm_api_key="sk-test",
        )
        UserService.update_llm_config(db_session, created.id, config_set)
        db_session.refresh(created)
        assert created.has_custom_llm_key is True
        config_clear = UserLLMConfigUpdate(llm_api_key="")
        UserService.update_llm_config(db_session, created.id, config_clear)
        db_session.refresh(created)
        assert created.has_custom_llm_key is False
