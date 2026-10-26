from datetime import datetime, timezone
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base


class QACacheEntry(Base):
    """
    语义缓存条目：历史"问题→回答"对及其向量，用于相似问题免调用 LLM。

    按用户隔离（BYOK 场景下不同用户的问答互不可见）。
    hit_count 只统计命中次数（首次入库不算命中）；
    prompt/completion_tokens 记录原始调用用量，用于折算每次命中节省的成本。
    """

    __tablename__ = "qa_cache_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # 命中时原样返回的来源快照；聊天链路缓存可为空，RAG 命中要求非空
    source_chunks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    embedding = mapped_column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    # 原始调用的用量与成本（按定价中心折算），命中时以此为"节省金额"
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    original_cost_cny: Mapped[float] = mapped_column(Float, default=0.0)

    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
