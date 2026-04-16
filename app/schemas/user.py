from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserBase(BaseModel):
    """
    所有 User 模型共用的基础字段
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    full_name: Optional[str] = Field(None, description="全名（可选）")

class UserCreate(UserBase):
    """
    创建用户时所需的字段（请求模型）
    """
    password: str = Field(..., min_length=6, description="密码")

class UserOut(UserBase):
    """
    返回给客户端的用户字段（响应模型），去除了密码等敏感信息
    """
    id: int
    is_active: bool = True

    class Config:
        from_attributes = True  # 未来方便从 SQLAlchemy 模型直接转换为 Pydantic 模型
