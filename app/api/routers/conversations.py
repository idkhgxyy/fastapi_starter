from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationMessageOut,
    ConversationOut,
)
from app.services import conversation_service

router = APIRouter()


def _to_out(conversation, message_count: int = 0) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        message_count=message_count,
    )


@router.post(
    "/",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
    summary="新建会话",
)
async def create_conversation(
    payload: Optional[ConversationCreate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    title = (payload.title if payload else None) or conversation_service.DEFAULT_TITLE
    conversation = conversation_service.create_conversation(
        db, user_id=current_user.id, title=title
    )
    return _to_out(conversation)


@router.get("/", response_model=List[ConversationOut], summary="当前用户的会话列表")
async def list_conversations(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    limit = max(1, min(limit, 200))
    rows = conversation_service.list_conversations_with_counts(
        db, user_id=current_user.id, limit=limit
    )
    return [_to_out(conversation, count) for conversation, count in rows]


@router.get("/{conversation_id}", response_model=ConversationDetail, summary="会话详情")
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conversation = conversation_service.get_conversation_for_user(
        db, conversation_id=conversation_id, user_id=current_user.id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = conversation_service.list_messages(db, conversation_id=conversation_id)
    return ConversationDetail(
        **_to_out(conversation, len(messages)).model_dump(),
        messages=[
            ConversationMessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at.isoformat(),
            )
            for message in messages
        ],
    )


@router.delete("/{conversation_id}", summary="删除会话（连同其消息）")
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    deleted = conversation_service.delete_conversation(
        db, conversation_id=conversation_id, user_id=current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": "会话已删除", "conversation_id": conversation_id}
