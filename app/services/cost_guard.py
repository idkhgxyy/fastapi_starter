"""LLM 成本熔断（Cost Circuit Breaker）。

背景：云端模型按 token 计费，供应商没有"余额用尽自动停服"开关，
超支部分直接按量扣真实余额。本模块基于 llm_call_logs 中已记录的
token 用量、按各模型单价折算累计花费，达到红线后拒绝后续调用。

设计要点：
- 数据源与 LLM Observability 同源（llm_call_logs 表），天然持久化，
  进程重启后花费不归零。
- 计价按"忙时价"保守估计，闲时实际花费只会更低，不会突破红线。
- 花费按用户维度统计：BYOK 模式下每个用户的 Key 只扣自己的账户，
  各用户的预算互不影响；user_id 为空（全局 Key 调用）时视为同一桶。
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.llm_call_log import LLMCallLog

# 已知模型单价表（元 / 百万 token，忙时价，来源：百炼官方价格页 2026-10）
# 未收录的模型回退到 settings 中的全局单价。
MODEL_PRICES_CNY_PER_1M = {
    "deepseek-v4-flash-0731": (3.0, 9.0),
    "deepseek-v4.1-flash": (2.0, 8.0),
    "deepseek-v3.2": (2.0, 3.0),
}


def get_model_prices(model_name: str) -> tuple:
    """返回 (输入单价, 输出单价)，单位：元/百万 token"""
    return MODEL_PRICES_CNY_PER_1M.get(
        model_name,
        (settings.LLM_INPUT_PRICE_PER_1M, settings.LLM_OUTPUT_PRICE_PER_1M),
    )


def estimate_cost_cny(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """按模型单价估算单次调用花费（元）"""
    input_price, output_price = get_model_prices(model_name)
    cost = prompt_tokens * input_price / 1_000_000 + completion_tokens * output_price / 1_000_000
    return round(cost, 6)


@dataclass
class BudgetStatus:
    allowed: bool
    spent_cny: float
    budget_cny: float

    @property
    def remaining_cny(self) -> float:
        return max(self.budget_cny - self.spent_cny, 0.0)


def get_spent_cny(db: Session, user_id: Optional[int]) -> float:
    """从调用日志重算累计花费（元）。

    不信任日志中存储的 estimated_cost_usd 字段（旧数据单价为 0），
    而是按每行的模型名与 token 数重新折算。
    """
    stmt = select(
        LLMCallLog.model_name,
        LLMCallLog.prompt_tokens,
        LLMCallLog.completion_tokens,
    ).where(LLMCallLog.status == "success")
    if user_id is not None:
        stmt = stmt.where(LLMCallLog.user_id == user_id)
    rows = db.execute(stmt).all()
    return round(
        sum(estimate_cost_cny(model, p, c) for model, p, c in rows),
        6,
    )


def check_budget(db: Session, user_id: Optional[int]) -> BudgetStatus:
    """检查该用户的累计花费是否已触及红线。

    budget <= 0 表示关闭熔断，恒放行。
    """
    budget = settings.LLM_BUDGET_CNY
    spent = get_spent_cny(db, user_id)
    allowed = budget <= 0 or spent < budget
    if not allowed:
        logger.warning(
            f"成本熔断触发: user_id={user_id} 已花费 {spent} 元, "
            f"达到红线 {budget} 元, 拒绝后续 LLM 调用"
        )
    return BudgetStatus(allowed=allowed, spent_cny=spent, budget_cny=budget)


def budget_reject_message(status: BudgetStatus) -> str:
    return (
        f"【成本熔断】LLM 调用已被拒绝：累计花费约 {status.spent_cny:.2f} 元，"
        f"已达到红线 {status.budget_cny:.0f} 元。"
        f"如需继续使用，请调整 LLM_BUDGET_CNY 配置或更换计费方案。"
    )
