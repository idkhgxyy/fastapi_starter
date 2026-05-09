from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
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

    @property
    def has_custom_llm_key(self) -> bool:
        return bool(self.llm_api_key_encrypted)
