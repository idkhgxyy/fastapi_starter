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


class UserBudgetUpdate(BaseModel):
    """用户更新个人成本预算；budget_cny 为 null 表示回退全局默认，<=0 表示关闭熔断"""

    budget_cny: Optional[float] = Field(None, description="个人预算（元/周期）")
    budget_period: Optional[str] = Field("monthly", description="预算周期，目前仅支持 monthly")


class UserBudgetOut(BaseModel):
    budget_cny: float = Field(..., description="生效预算（元/周期，含全局回退）")
    budget_period: str = Field("monthly", description="预算周期")
    has_personal_budget: bool = Field(..., description="是否设置了个人预算")
    spent_cny: float = Field(..., description="当前周期已花费（元）")
    remaining_cny: float = Field(..., description="当前周期剩余（元）")
    period_start: Optional[str] = Field(None, description="当前周期起点 (ISO)")
