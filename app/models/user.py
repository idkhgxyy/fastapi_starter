from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """
    用户数据库模型
    对应 PostgreSQL 中的 users 表
    """

    __tablename__ = "users"

    # 使用 SQLAlchemy 2.0 的新语法 Mapped 和 mapped_column
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 存储密码哈希值，避免在数据库中保留明文密码。
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # 用户级 LLM 配置 (可选，支持多租户独立 LLM)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    llm_model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    llm_api_key_encrypted: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 用户级成本预算（BYOK 场景下保护用户自己的钱包）
    # budget_cny 为 NULL 时回退到全局默认 LLM_BUDGET_CNY；<=0 表示关闭熔断
    budget_cny: Mapped[Optional[float]] = mapped_column(nullable=True)
    # 目前仅支持 'monthly'（自然月重置），预留扩展
    budget_period: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="monthly")

    @property
    def has_custom_llm_key(self) -> bool:
        return bool(self.llm_api_key_encrypted)
