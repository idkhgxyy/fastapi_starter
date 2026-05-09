from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import generate_chat_reply, generate_chat_reply_stream
from app.models.user import User
from app.api.deps import get_current_user, get_db
from app.utils.rate_limit import RateLimiter

router = APIRouter()

# 聊天接口，使用限流器：同一个客户端每 60 秒最多 20 次请求
@router.post("/", summary="与 AI 进行对话", dependencies=[Depends(RateLimiter(times=20, seconds=60))])
async def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # 默认只有登录用户可以聊天
):
    """
    基础对话接口（支持 Tool Calling 与 SSE 流式输出）。
    要求用户在 Header 中携带 JWT Token 才能访问。
    """
    if request.stream:
        # 流式返回
        return StreamingResponse(
            generate_chat_reply_stream(message=request.message, db=db, current_user_id=current_user.id),
            media_type="text/event-stream"
        )
    else:
        # 阻塞返回
        reply = await generate_chat_reply(
            message=request.message,
            db=db,
            current_user_id=current_user.id
        )
        return ChatResponse(reply=reply)
