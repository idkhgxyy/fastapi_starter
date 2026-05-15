from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    is_superuser: bool = False

    # 返回给客户端的配置，这里不返回 encrypted_api_key，而是返回是否已配置
    llm_provider: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_name: Optional[str] = None
    has_custom_llm_key: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserLLMConfigUpdate(BaseModel):
    """
    用户更新自定义 LLM 配置
    """

    llm_provider: Optional[str] = Field(None, description="LLM 服务商")
    llm_base_url: Optional[str] = Field(None, description="LLM Base URL")
    llm_model_name: Optional[str] = Field(None, description="LLM 模型名称")
    llm_api_key: Optional[str] = Field(None, description="LLM API Key (明文，入库时会被加密)")


class PasswordUpdate(BaseModel):
    old_password: str = Field(..., min_length=6, description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")
