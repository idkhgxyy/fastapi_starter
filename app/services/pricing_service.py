"""模型定价中心。

单价数据的唯一可信来源是 model_pricings 表；表中无记录时回退到
settings 全局单价（作为兜底）。查询结果带 TTL 内存缓存，避免每次
调用/统计都打数据库。

价格口径：元/百万 token，忙时价（保守估计，闲时实际花费更低）。
"""

import time
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.model_pricing import ModelPricing

# 内存缓存：{model_name: ((input_price, output_price), fetched_at)}
_PRICE_CACHE: dict = {}
_CACHE_TTL_SECONDS = 60

# 内置种子价格（2026-10 查自百炼官方价格页，忙时价）
DEFAULT_PRICINGS = [
    {"model_name": "deepseek-v4.1-flash", "input": 2.0, "output": 8.0,
     "note": "百炼官方价，忙时；闲时 1/4"},
    {"model_name": "deepseek-v4-flash-0731", "input": 3.0, "output": 9.0,
     "note": "百炼官方价，忙时；闲时 1.5/4.5"},
    {"model_name": "deepseek-v3.2", "input": 2.0, "output": 3.0,
     "note": "百炼官方价"},
]


def seed_default_pricings(db: Session) -> int:
    """幂等写入内置种子价格，返回新插入的条数。应用启动时调用。"""
    inserted = 0
    try:
        existing = {
            name for (name,) in db.query(ModelPricing.model_name).all()
        }
        for item in DEFAULT_PRICINGS:
            if item["model_name"] in existing:
                continue
            db.add(
                ModelPricing(
                    model_name=item["model_name"],
                    input_price_per_1m=item["input"],
                    output_price_per_1m=item["output"],
                    currency="CNY",
                    note=item["note"],
                )
            )
            inserted += 1
        if inserted:
            db.commit()
            _PRICE_CACHE.clear()
            logger.info(f"定价中心: 已写入 {inserted} 条内置模型单价")
    except Exception as e:
        db.rollback()
        logger.warning(f"定价中心: 种子数据写入失败（不影响启动）: {e}")
    return inserted


def get_model_prices(db: Session, model_name: str) -> Tuple[float, float]:
    """查询单价 (输入, 输出)，单位 元/百万 token。

    查找顺序：内存缓存(60s) → model_pricings 表 → settings 全局兜底。
    """
    cached = _PRICE_CACHE.get(model_name)
    if cached and time.monotonic() - cached[1] < _CACHE_TTL_SECONDS:
        return cached[0]

    try:
        row = (
            db.query(ModelPricing)
            .filter(ModelPricing.model_name == model_name)
            .first()
        )
        if row is not None:
            prices = (row.input_price_per_1m, row.output_price_per_1m)
            _PRICE_CACHE[model_name] = (prices, time.monotonic())
            return prices
    except Exception as e:
        logger.warning(f"定价中心: 查询 {model_name} 单价失败，使用兜底价格: {e}")

    prices = (settings.LLM_INPUT_PRICE_PER_1M, settings.LLM_OUTPUT_PRICE_PER_1M)
    _PRICE_CACHE[model_name] = (prices, time.monotonic())
    return prices


def estimate_cost_cny(
    db: Session, model_name: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """按定价中心折算单次调用花费（元）"""
    input_price, output_price = get_model_prices(db, model_name)
    cost = prompt_tokens * input_price / 1_000_000 + completion_tokens * output_price / 1_000_000
    return round(cost, 6)


def invalidate_cache() -> None:
    """价格被修改后调用，强制下次查询重新读库"""
    _PRICE_CACHE.clear()
