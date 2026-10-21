from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

AGENT_TASK_STATUS_PENDING = "pending"
AGENT_TASK_STATUS_RUNNING = "running"
AGENT_TASK_STATUS_SUCCEEDED = "succeeded"
AGENT_TASK_STATUS_FAILED = "failed"

AGENT_STEP_STATUS_PENDING = "pending"
AGENT_STEP_STATUS_RUNNING = "running"
AGENT_STEP_STATUS_SUCCEEDED = "succeeded"
AGENT_STEP_STATUS_FAILED = "failed"


class AgentTask(Base):
    """目标型任务：描述一个目标，由后台流水线产出一份 Markdown 成果。"""

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AGENT_TASK_STATUS_PENDING, index=True
    )
    # None = 自动检索该用户全部已就绪文档；否则只用列出的文档
    scope_document_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    output_type: Mapped[str] = mapped_column(String(20), nullable=False, default="markdown")

    result_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cny: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    steps = relationship(
        "AgentTaskStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="AgentTaskStep.seq",
    )


class AgentTaskStep(Base):
    __tablename__ = "agent_task_steps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AGENT_TASK_STATUS_PENDING
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cny: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    task = relationship("AgentTask", back_populates="steps")
