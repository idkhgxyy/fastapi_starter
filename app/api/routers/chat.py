from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import generate_chat_reply
from app.models.user import User
from app.api.deps import get_current_user, get_db

router = APIRouter()

@router.post("/", response_model=ChatResponse, summary="与 AI 进行对话")
async def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # 默认只有登录用户可以聊天
):
    """
    基础对话接口（最小化 LLM 接入）。
    要求用户在 Header 中携带 JWT Token 才能访问。
    """
    reply = await generate_chat_reply(
        message=request.message,
        db=db,
        current_user_id=current_user.id
    )
    return ChatResponse(reply=reply)
