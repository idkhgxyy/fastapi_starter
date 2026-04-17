from pydantic import BaseModel

class Token(BaseModel):
    """
    登录成功后返回的 Token 格式
    """
    access_token: str
    token_type: str

from typing import Optional

class TokenPayload(BaseModel):
    """
    解析 Token 时内部使用的载荷格式
    """
    sub: Optional[str] = None
