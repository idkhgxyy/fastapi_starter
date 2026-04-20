from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.llm_call_log import LLMCallLog
from app.models.user import User
from app.schemas.observability import LLMCallLogOut, LLMStatsResponse
from app.services.llm_observability_service import get_llm_overview_stats

router = APIRouter()


@router.get("/llm-stats", response_model=LLMStatsResponse, summary="获取 LLM 调用统计")
async def get_llm_stats(
    days: int = Query(7, ge=1, le=30, description="统计最近 N 天的数据"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    普通用户查看自己的 LLM 调用统计；超级管理员查看全量统计。
    """
    scoped_user_id = None if current_user.is_superuser else current_user.id
    return get_llm_overview_stats(db, user_id=scoped_user_id, days=days)


@router.get("/llm-calls", response_model=list[LLMCallLogOut], summary="查看最近的 LLM 调用记录")
async def list_llm_calls(
    limit: int = Query(20, ge=1, le=100, description="返回最近多少条日志"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(LLMCallLog)
    if not current_user.is_superuser:
        query = query.filter(LLMCallLog.user_id == current_user.id)

    logs = query.order_by(LLMCallLog.created_at.desc()).limit(limit).all()
    return [
        LLMCallLogOut(
            id=log.id,
            endpoint=log.endpoint,
            model_name=log.model_name,
            provider=log.provider,
            request_id=log.request_id,
            prompt=log.prompt,
            response=log.response,
            tool_calls=log.tool_calls,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            total_tokens=log.total_tokens,
            latency_ms=log.latency_ms,
            estimated_cost_usd=log.estimated_cost_usd,
            status=log.status,
            error_message=log.error_message,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
