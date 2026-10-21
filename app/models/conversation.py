from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conversation(Base):
    """一次完整的对话（会话）。消息存在独立的表里，便于按会话裁剪与后续做消息级功能。"""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 由首条用户消息自动生成，不调用 LLM（省一次请求）
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新对话")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        index=True,
    )

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id",
    )

    __table_args__ = (
        # 会话列表查询是最高频的：按用户过滤 + 按更新时间倒序
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        # 按会话取消息并按 id 排序，覆盖索引直接支撑该查询
        Index("ix_conversation_messages_conv_id", "conversation_id", "id"),
    )


def build_conversation_title(first_message: str, max_length: int = 30) -> str:
    """用首条用户消息生成标题：压缩空白、截断，不额外调用 LLM。"""
    compact = " ".join(first_message.split())
    if not compact:
        return "新对话"
    if len(compact) <= max_length:
        return compact
    return compact[:max_length] + "…"


__all__ = ["Conversation", "ConversationMessage", "build_conversation_title"]
