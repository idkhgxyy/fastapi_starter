from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AgentTaskCreate(BaseModel):
    goal: str = Field(..., min_length=2, max_length=2000, description="想要达成的目标")
    scope_mode: Literal["auto", "selected"] = Field(
        "auto", description="auto=自动使用全部已就绪文档；selected=只用 document_ids"
    )
    document_ids: List[int] = Field(default_factory=list, description="scope_mode=selected 时生效")


class AgentTaskStepOut(BaseModel):
    seq: int
    name: str
    status: str
    summary: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    cost_cny: float
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class AgentTaskOut(BaseModel):
    id: int
    title: str
    goal: str
    status: str
    output_type: str
    scope_document_ids: Optional[List[int]] = None
    error_message: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    cost_cny: float
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class AgentTaskDetail(AgentTaskOut):
    result_markdown: Optional[str] = None
    steps: List[AgentTaskStepOut] = Field(default_factory=list)
