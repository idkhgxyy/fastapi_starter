from typing import List, Optional

from pydantic import BaseModel, Field


class ConversationMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(ConversationOut):
    messages: List[ConversationMessageOut]


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="可选，默认「新对话」")
