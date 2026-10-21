from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.document import DOCUMENT_STATUS_READY, Document
from app.models.user import User
from app.schemas.agent_task import (
    AgentTaskCreate,
    AgentTaskDetail,
    AgentTaskOut,
    AgentTaskStepOut,
)
from app.services import agent_task_service
from app.services.cost_guard import budget_reject_message, check_budget
from app.worker.tasks import run_agent_task_task

router = APIRouter()


def _iso(value):
    return value.isoformat() if value else None


def _to_out(task) -> AgentTaskOut:
    return AgentTaskOut(
        id=task.id,
        title=task.title,
        goal=task.goal,
        status=task.status,
        output_type=task.output_type,
        scope_document_ids=task.scope_document_ids,
        error_message=task.error_message,
        prompt_tokens=task.prompt_tokens,
        completion_tokens=task.completion_tokens,
        cost_cny=round(task.cost_cny, 6),
        created_at=task.created_at.isoformat(),
        started_at=_iso(task.started_at),
        finished_at=_iso(task.finished_at),
    )


def _to_detail(task) -> AgentTaskDetail:
    base = _to_out(task).model_dump()
    return AgentTaskDetail(
        **base,
        result_markdown=task.result_markdown,
        steps=[
            AgentTaskStepOut(
                seq=step.seq,
                name=step.name,
                status=step.status,
                summary=step.summary,
                prompt_tokens=step.prompt_tokens,
                completion_tokens=step.completion_tokens,
                cost_cny=round(step.cost_cny, 6),
                started_at=_iso(step.started_at),
                finished_at=_iso(step.finished_at),
            )
            for step in task.steps
        ],
    )


@router.post(
    "/",
    response_model=AgentTaskOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建目标型任务并在后台生成成果",
)
async def create_agent_task(
    payload: AgentTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    budget = check_budget(db, current_user.id)
    if not budget.allowed:
        raise HTTPException(status_code=402, detail=budget_reject_message(budget))

    document_ids = None
    if payload.scope_mode == "selected":
        if not payload.document_ids:
            raise HTTPException(status_code=400, detail="请选择至少一篇文档，或切换为自动模式。")
        rows = (
            db.execute(
                select(Document.id).where(
                    Document.owner_id == current_user.id,
                    Document.id.in_(payload.document_ids),
                    Document.status == DOCUMENT_STATUS_READY,
                )
            )
            .scalars()
            .all()
        )
        if len(set(rows)) != len(set(payload.document_ids)):
            raise HTTPException(status_code=400, detail="部分文档不存在、不属于你或尚未处理完成。")
        document_ids = sorted(set(payload.document_ids))

    task = agent_task_service.create_task(
        db, user_id=current_user.id, goal=payload.goal, document_ids=document_ids
    )
    run_agent_task_task.delay(task.id)
    return _to_out(task)


@router.get("/", response_model=List[AgentTaskOut], summary="当前用户的目标任务列表")
async def list_agent_tasks(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    limit = max(1, min(limit, 200))
    return [
        _to_out(task)
        for task in agent_task_service.list_tasks(db, user_id=current_user.id, limit=limit)
    ]


@router.get("/{task_id}", response_model=AgentTaskDetail, summary="任务详情与成果")
async def get_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = agent_task_service.get_task_for_user(db, task_id=task_id, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=404, detail="Agent task not found.")
    return _to_detail(task)


@router.post("/{task_id}/retry", response_model=AgentTaskOut, summary="重试失败的任务")
async def retry_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = agent_task_service.get_task_for_user(db, task_id=task_id, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=404, detail="Agent task not found.")
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="只有失败的任务可以重试。")

    budget = check_budget(db, current_user.id)
    if not budget.allowed:
        raise HTTPException(status_code=402, detail=budget_reject_message(budget))

    task = agent_task_service.reset_for_retry(db, task=task)
    run_agent_task_task.delay(task.id)
    return _to_out(task)


@router.delete("/{task_id}", summary="删除任务与它的步骤")
async def delete_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    deleted = agent_task_service.delete_task(db, task_id=task_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent task not found.")
    return {"message": "任务已删除", "task_id": task_id}


@router.get("/{task_id}/export", summary="导出 Markdown 成果")
async def export_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    task = agent_task_service.get_task_for_user(db, task_id=task_id, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=404, detail="Agent task not found.")
    if not task.result_markdown:
        raise HTTPException(status_code=400, detail="任务还没有可导出的成果。")

    return Response(
        content=task.result_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="agent-task-{task.id}.md"'},
    )
