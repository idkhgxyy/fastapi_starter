from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户的输入消息", min_length=1)
    stream: bool = Field(False, description="是否使用 SSE 流式输出")
    session_id: Optional[str] = Field(
        None, max_length=64, description="会话 ID（同一次多轮对话传相同值即可携带上下文）"
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="大语言模型的回复")
