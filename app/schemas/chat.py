from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户的输入消息", min_length=1)
    stream: bool = Field(False, description="是否使用 SSE 流式输出")
    session_id: Optional[str] = Field(
        None, max_length=64, description="会话 ID（遗留参数，RAG 查询使用）"
    )
    conversation_id: Optional[int] = Field(
        None, description="会话 ID；传入后历史从数据库读写，刷新/断线不丢"
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="大语言模型的回复")
