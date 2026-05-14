import jwt
from datetime import timedelta

from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.core.config import settings


class TestPasswordHashing:
    def test_hash_returns_different_from_plain(self):
        hashed = get_password_hash("my_password")
        assert hashed != "my_password"
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_same_input_produces_different_hash(self):
        h1 = get_password_hash("stable")
        h2 = get_password_hash("stable")
        assert h1 != h2

    def test_long_password_truncated_to_72_bytes(self):
        long_pass = "a" * 100
        hashed = get_password_hash(long_pass)
        assert verify_password(long_pass, hashed) is True


class TestJWT:
    def test_create_and_decode_token(self):
        data = {"sub": "42"}
        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_token_with_custom_expiry(self):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_token_invalid_signature(self):
        wrong_token = jwt.encode({"sub": "1"}, "wrong_secret", algorithm="HS256")
        try:
            jwt.decode(wrong_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            assert False, "should have raised"
        except jwt.PyJWTError:
            assert True

    def test_token_expired(self):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
        try:
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            assert False, "should have raised"
        except jwt.PyJWTError:
            assert True

    def test_token_for_different_users(self):
        token_a = create_access_token({"sub": "10"})
        token_b = create_access_token({"sub": "20"})
        payload_a = jwt.decode(token_a, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        payload_b = jwt.decode(token_b, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload_a["sub"] != payload_b["sub"]
