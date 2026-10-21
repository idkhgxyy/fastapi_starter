"""会话与消息的持久化服务。

聊天历史以数据库为准；Redis 只保留给 RAG 查询接口的 session 机制。
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.conversation import (
    Conversation,
    ConversationMessage,
    build_conversation_title,
)

DEFAULT_TITLE = "新对话"


def create_conversation(db: Session, *, user_id: int, title: str = DEFAULT_TITLE) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations_with_counts(
    db: Session, *, user_id: int, limit: int = 50
) -> List[tuple[Conversation, int]]:
    """按更新时间倒序返回 (会话, 消息数)。"""
    stmt = (
        select(Conversation, func.count(ConversationMessage.id))
        .outerjoin(
            ConversationMessage,
            ConversationMessage.conversation_id == Conversation.id,
        )
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def get_conversation_for_user(
    db: Session, *, conversation_id: int, user_id: int
) -> Optional[Conversation]:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def delete_conversation(db: Session, *, conversation_id: int, user_id: int) -> bool:
    conversation = get_conversation_for_user(db, conversation_id=conversation_id, user_id=user_id)
    if conversation is None:
        return False
    db.delete(conversation)
    db.commit()
    return True


def list_messages(
    db: Session, *, conversation_id: int, limit: Optional[int] = None
) -> List[ConversationMessage]:
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.id)
    )
    if limit is not None:
        # 超出上限时保留最近的 N 条，但返回仍按时间正序
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id.desc())
            .limit(limit)
        )
        rows = list(db.execute(stmt).scalars().all())
        rows.reverse()
        return rows
    return list(db.execute(stmt).scalars().all())


def load_history_for_prompt(db: Session, *, conversation_id: int, limit: int) -> List[dict]:
    """给 LLM 用的历史消息（最近 limit 条，按时间正序）。"""
    return [
        {"role": message.role, "content": message.content}
        for message in list_messages(db, conversation_id=conversation_id, limit=limit)
        if message.role in ("user", "assistant") and message.content
    ]


def append_exchange(
    db: Session,
    *,
    conversation: Conversation,
    user_content: str,
    assistant_content: str,
) -> None:
    """一轮问答结束后落库，并在首轮自动生成标题。"""
    has_previous = bool(
        db.scalar(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.conversation_id == conversation.id
            )
        )
    )
    db.add(ConversationMessage(conversation_id=conversation.id, role="user", content=user_content))
    db.add(
        ConversationMessage(
            conversation_id=conversation.id, role="assistant", content=assistant_content
        )
    )
    if not has_previous and conversation.title in (None, "", DEFAULT_TITLE):
        conversation.title = build_conversation_title(user_content)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
