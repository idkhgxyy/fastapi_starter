"""LLM 成本熔断（Cost Circuit Breaker）。

背景：云端模型按 token 计费，供应商没有"余额用尽自动停服"开关，
超支部分直接按量扣真实余额。本模块基于 llm_call_logs 中已记录的
token 用量、按定价中心折算累计花费，达到红线后拒绝后续调用。

设计要点：
- 数据源与 LLM Observability 同源（llm_call_logs 表），天然持久化，
  进程重启后花费不归零。
- 单价来自定价中心（model_pricings 表，忙时价保守估计），闲时实际
  花费只会更低，不会突破红线。
- 花费按用户维度统计：BYOK 模式下每个用户的 Key 只扣自己的账户，
  各用户的预算互不影响；user_id 为空（全局 Key 调用）时视为同一桶。
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.llm_call_log import LLMCallLog
from app.models.user import User
from app.services.pricing_service import estimate_cost_cny

SUPPORTED_BUDGET_PERIODS = ("monthly",)


@dataclass
class BudgetStatus:
    allowed: bool
    spent_cny: float
    budget_cny: float
    period: str = "monthly"
    period_start: Optional[datetime] = None

    @property
    def remaining_cny(self) -> float:
        return max(self.budget_cny - self.spent_cny, 0.0)


def _period_start(period: str) -> Optional[datetime]:
    """返回当前周期的起点（UTC，naive，与 llm_call_logs.created_at 存储格式一致）"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


def get_spent_cny(
    db: Session, user_id: Optional[int], since: Optional[datetime] = None
) -> float:
    """从调用日志重算累计花费（元）。

    不信任日志中存储的 estimated_cost_usd 字段（旧数据单价为 0），
    而是按每行的模型名与 token 数、经定价中心重新折算。
    since 传入时只统计该时间点之后的花费（用于周期预算）。
    """
    stmt = select(
        LLMCallLog.model_name,
        LLMCallLog.prompt_tokens,
        LLMCallLog.completion_tokens,
    ).where(LLMCallLog.status == "success")
    if user_id is not None:
        stmt = stmt.where(LLMCallLog.user_id == user_id)
    if since is not None:
        stmt = stmt.where(LLMCallLog.created_at >= since)
    rows = db.execute(stmt).all()
    return round(
        sum(estimate_cost_cny(db, model, p, c) for model, p, c in rows),
        6,
    )


def _resolve_budget(user: Optional[User]) -> float:
    """用户设置了个人预算用个人的，否则回退全局默认（<=0 表示关闭熔断）"""
    if user is not None and user.budget_cny is not None:
        return user.budget_cny
    return settings.LLM_BUDGET_CNY


def check_budget(db: Session, user_id: Optional[int]) -> BudgetStatus:
    """检查该用户当前周期内累计花费是否已触及预算红线。

    - 预算按自然月计算（月初重置）；无个人预算时回退全局 LLM_BUDGET_CNY
    - budget <= 0 表示关闭熔断，恒放行
    """
    user = db.get(User, user_id) if user_id is not None else None
    budget = _resolve_budget(user)
    period = (user.budget_period if user and user.budget_period else "monthly") or "monthly"
    period_start = _period_start(period)

    spent = get_spent_cny(db, user_id, since=period_start)
    allowed = budget <= 0 or spent < budget
    if not allowed:
        period_label = "本月" if period == "monthly" else "本周期"
        logger.warning(
            f"成本熔断触发: user_id={user_id} {period_label}已花费 "
            f"{spent} 元, 达到预算 {budget} 元, 拒绝后续 LLM 调用"
        )
    return BudgetStatus(
        allowed=allowed,
        spent_cny=spent,
        budget_cny=budget,
        period=period,
        period_start=period_start,
    )


def budget_reject_message(status: BudgetStatus) -> str:
    period_label = "本月" if status.period == "monthly" else "本周期"
    return (
        f"【成本熔断】LLM 调用已被拒绝：{period_label}累计花费约 {status.spent_cny:.2f} 元，"
        f"已达到预算 {status.budget_cny:.0f} 元（月初自动重置）。"
        f"如需继续使用，请在设置中调整个人预算。"
    )
