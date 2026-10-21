from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import conversation_service
from app.services.llm_service import generate_chat_reply, generate_chat_reply_stream
from app.utils.rate_limit import RateLimiter

router = APIRouter()


# 聊天接口，使用限流器：同一个客户端每 60 秒最多 20 次请求
@router.post(
    "/", summary="与 AI 进行对话", dependencies=[Depends(RateLimiter(times=20, seconds=60))]
)
async def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 默认只有登录用户可以聊天
):
    """
    基础对话接口（支持 Tool Calling 与 SSE 流式输出）。
    要求用户在 Header 中携带 JWT Token 才能访问。

    传入 conversation_id 时，历史从数据库读写（持久化）；不传则退回 Redis session 机制。
    """
    conversation = None
    if request.conversation_id is not None:
        conversation = conversation_service.get_conversation_for_user(
            db, conversation_id=request.conversation_id, user_id=current_user.id
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")

    if request.stream:
        # 流式返回
        return StreamingResponse(
            generate_chat_reply_stream(
                message=request.message,
                db=db,
                current_user_id=current_user.id,
                session_id=request.session_id,
                conversation=conversation,
            ),
            media_type="text/event-stream",
        )
    else:
        # 阻塞返回
        reply = await generate_chat_reply(
            message=request.message,
            db=db,
            current_user_id=current_user.id,
            session_id=request.session_id,
            conversation=conversation,
        )
        return ChatResponse(reply=reply)
