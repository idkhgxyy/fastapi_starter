from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelPricing(Base):
    """
    模型定价中心：每个模型一条记录，单价单位为 元/百万 token（忙时价，保守估计）。
    成本熔断、用量统计、缓存节省计算均以此表为准；
    表中无记录的模型回退到 settings 中的全局单价。
    """

    __tablename__ = "model_pricings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    input_price_per_1m: Mapped[float] = mapped_column(Float, nullable=False)
    output_price_per_1m: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    note: Mapped[str] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
