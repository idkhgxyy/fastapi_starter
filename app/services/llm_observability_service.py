import json
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_request_id, logger
from app.models.llm_call_log import LLMCallLog


def start_timer() -> float:
    return perf_counter()


def elapsed_ms(start_time: float) -> float:
    return round((perf_counter() - start_time) * 1000, 2)


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    input_cost = (prompt_tokens / 1000) * settings.LLM_INPUT_PRICE_PER_1K_TOKENS
    output_cost = (completion_tokens / 1000) * settings.LLM_OUTPUT_PRICE_PER_1K_TOKENS
    return round(input_cost + output_cost, 6)


def extract_usage(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if not usage:
        return 0, 0, 0
    return (
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
        getattr(usage, "total_tokens", 0) or 0,
    )


def serialize_tool_calls(tool_calls: Optional[Iterable[Any]]) -> Optional[str]:
    if not tool_calls:
        return None

    normalized = []
    for tool_call in tool_calls:
        normalized.append(
            {
                "id": getattr(tool_call, "id", None),
                "name": getattr(tool_call.function, "name", None),
                "arguments": getattr(tool_call.function, "arguments", None),
            }
        )
    return json.dumps(normalized, ensure_ascii=False)


def create_llm_call_log(
    db: Session,
    *,
    user_id: Optional[int],
    endpoint: str,
    prompt: str,
    response: Optional[str],
    tool_calls: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: float,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    try:
        log = LLMCallLog(
            user_id=user_id,
            endpoint=endpoint,
            model_name=settings.LLM_MODEL_NAME,
            provider=settings.LLM_PROVIDER,
            request_id=get_request_id(),
            prompt=prompt,
            response=response,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=estimate_cost_usd(prompt_tokens, completion_tokens),
            status=status,
            error_message=error_message,
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"写入 LLM 调用日志失败: {exc}")


def get_llm_overview_stats(db: Session, *, user_id: Optional[int] = None, days: int = 7) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    base_query = db.query(LLMCallLog).filter(LLMCallLog.created_at >= cutoff)
    if user_id is not None:
        base_query = base_query.filter(LLMCallLog.user_id == user_id)

    rows = base_query.all()
    total_calls = len(rows)
    successful_calls = len([row for row in rows if row.status == "success"])
    failed_calls = total_calls - successful_calls
    total_tokens = sum(row.total_tokens for row in rows)
    total_cost = round(sum(row.estimated_cost_usd for row in rows), 6)
    avg_latency_ms = round(sum(row.latency_ms for row in rows) / total_calls, 2) if total_calls else 0.0

    daily_query = db.query(
        func.date(LLMCallLog.created_at).label("day"),
        func.count(LLMCallLog.id).label("calls"),
        func.sum(LLMCallLog.total_tokens).label("tokens"),
        func.sum(LLMCallLog.estimated_cost_usd).label("cost"),
        func.avg(LLMCallLog.latency_ms).label("avg_latency_ms"),
    ).filter(LLMCallLog.created_at >= cutoff)
    if user_id is not None:
        daily_query = daily_query.filter(LLMCallLog.user_id == user_id)
    daily_query = daily_query.group_by(func.date(LLMCallLog.created_at)).order_by(func.date(LLMCallLog.created_at))

    daily_stats = [
        {
            "date": str(item.day),
            "calls": int(item.calls or 0),
            "tokens": int(item.tokens or 0),
            "cost_usd": round(float(item.cost or 0), 6),
            "avg_latency_ms": round(float(item.avg_latency_ms or 0), 2),
        }
        for item in daily_query.all()
    ]

    endpoint_query = db.query(
        LLMCallLog.endpoint,
        func.count(LLMCallLog.id).label("calls"),
        func.sum(LLMCallLog.total_tokens).label("tokens"),
    ).filter(LLMCallLog.created_at >= cutoff)
    if user_id is not None:
        endpoint_query = endpoint_query.filter(LLMCallLog.user_id == user_id)
    endpoint_query = endpoint_query.group_by(LLMCallLog.endpoint).order_by(func.count(LLMCallLog.id).desc())

    endpoint_stats = [
        {
            "endpoint": item.endpoint,
            "calls": int(item.calls or 0),
            "tokens": int(item.tokens or 0),
        }
        for item in endpoint_query.all()
    ]

    per_user_query = db.query(
        LLMCallLog.user_id,
        func.count(LLMCallLog.id).label("calls"),
        func.sum(LLMCallLog.total_tokens).label("tokens"),
        func.sum(LLMCallLog.estimated_cost_usd).label("cost"),
    ).filter(LLMCallLog.created_at >= cutoff)
    if user_id is not None:
        per_user_query = per_user_query.filter(LLMCallLog.user_id == user_id)
    per_user_query = per_user_query.group_by(LLMCallLog.user_id).order_by(func.count(LLMCallLog.id).desc())

    per_user_stats = [
        {
            "user_id": int(item.user_id or 0),
            "calls": int(item.calls or 0),
            "tokens": int(item.tokens or 0),
            "cost_usd": round(float(item.cost or 0), 6),
        }
        for item in per_user_query.all()
        if item.user_id is not None
    ]

    return {
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "avg_latency_ms": avg_latency_ms,
        "daily_stats": daily_stats,
        "endpoint_stats": endpoint_stats,
        "per_user_stats": per_user_stats,
    }
