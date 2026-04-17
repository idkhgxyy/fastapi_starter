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
    
    # 密码存入数据库必须哈希处理。今天 Day 5 为了先跑通流程暂时存明文，Day 7 我们会接入哈希算法！
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
