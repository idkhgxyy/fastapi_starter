from typing import List, Optional

from pydantic import BaseModel, Field


class LLMCallLogOut(BaseModel):
    id: int
    endpoint: str
    model_name: str
    provider: str
    request_id: Optional[str] = None
    prompt: str
    response: Optional[str] = None
    tool_calls: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    status: str
    error_message: Optional[str] = None
    created_at: str


class DailyLLMStats(BaseModel):
    date: str
    calls: int
    tokens: int
    cost_usd: float
    avg_latency_ms: float


class EndpointLLMStats(BaseModel):
    endpoint: str
    calls: int
    tokens: int


class UserLLMStats(BaseModel):
    user_id: int
    calls: int
    tokens: int
    cost_usd: float


class LLMStatsResponse(BaseModel):
    total_calls: int = Field(..., description="总调用次数")
    successful_calls: int = Field(..., description="成功次数")
    failed_calls: int = Field(..., description="失败次数")
    total_tokens: int = Field(..., description="总 token 数")
    total_cost_usd: float = Field(..., description="估算总成本（美元）")
    avg_latency_ms: float = Field(..., description="平均耗时（毫秒）")
    daily_stats: List[DailyLLMStats]
    endpoint_stats: List[EndpointLLMStats]
    per_user_stats: List[UserLLMStats]
