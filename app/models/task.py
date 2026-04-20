from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.base import Base

class Task(Base):
    """
    任务数据库模型
    对应 PostgreSQL 中的 tasks 表
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    # 状态：pending, in_progress, completed
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # 外键关联到 users 表
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关系属性，方便通过 task.owner 直接获取对应的 User 对象
    owner = relationship("User", backref="tasks")
