from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LLMCallLog(Base):
    """
    记录每一次 LLM 调用的核心信息，方便做排障、成本统计和效果复盘。
    """

    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(100), index=True)
    model_name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50), default="openai_compatible")
    request_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="success", index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", backref="llm_call_logs")
