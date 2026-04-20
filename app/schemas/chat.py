from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户的输入消息", min_length=1)

class ChatResponse(BaseModel):
    reply: str = Field(..., description="大语言模型的回复")
