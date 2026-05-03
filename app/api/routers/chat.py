from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import generate_chat_reply, generate_chat_reply_stream
from app.models.user import User
from app.api.deps import get_current_user, get_db, RateLimiter

router = APIRouter()

# 限流：每分钟最多 10 次对话请求
chat_rate_limiter = RateLimiter(times=10, seconds=60)

@router.post("/", response_model=ChatResponse, summary="与 AI 进行对话", dependencies=[Depends(chat_rate_limiter)])
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

@router.post("/stream", summary="与 AI 进行对话 (流式返回)", dependencies=[Depends(chat_rate_limiter)])
async def chat_with_ai_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    流式对话接口 (Server-Sent Events)
    """
    return StreamingResponse(
        generate_chat_reply_stream(
            message=request.message,
            db=db,
            current_user_id=current_user.id
        ),
        media_type="text/event-stream"
    )
