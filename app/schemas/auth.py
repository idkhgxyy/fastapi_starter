from typing import Optional

from pydantic import BaseModel, field_validator


class Token(BaseModel):
    """登录成功后返回的 Token 格式"""

    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """解析 Token 时内部使用的载荷格式"""

    sub: Optional[str] = None


class SetupStatus(BaseModel):
    """系统初始化状态"""

    initialized: bool
    llm_mock: bool
    llm_provider: str


class SetupRequest(BaseModel):
    """首次初始化请求"""

    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v
