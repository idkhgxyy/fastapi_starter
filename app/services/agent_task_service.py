"""目标型 Agent 任务的执行服务（固定流水线，不做自主规划）。

流水线：retrieve（收集材料）→ outline（生成大纲）→ write（逐节撰写）→ finalize（汇总）
每一步都落库，前端可以看进度；每次 LLM 调用都走定价中心记账与预算熔断。
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.agent_task import (
    AGENT_STEP_STATUS_FAILED,
    AGENT_STEP_STATUS_RUNNING,
    AGENT_STEP_STATUS_SUCCEEDED,
    AGENT_TASK_STATUS_FAILED,
    AGENT_TASK_STATUS_PENDING,
    AGENT_TASK_STATUS_RUNNING,
    AGENT_TASK_STATUS_SUCCEEDED,
    AgentTask,
    AgentTaskStep,
)
from app.models.document import DOCUMENT_STATUS_READY, Document
from app.models.user import User
from app.services.cost_guard import budget_reject_message, check_budget
from app.services.llm_observability_service import (
    create_llm_call_log,
    elapsed_ms,
    extract_usage,
    start_timer,
)
from app.services.llm_service import get_llm_client
from app.services.pricing_service import estimate_cost_cny
from app.services.rag_service import RAGService

FALLBACK_SECTIONS = ["背景与目标", "关键材料与现状", "分析与建议", "结论与下一步"]


class AgentTaskError(Exception):
    """可预期的任务失败（材料不足、预算触顶、未配置 Key 等）。"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_title(goal: str, max_length: int = 40) -> str:
    compact = " ".join(goal.split())
    if not compact:
        return "未命名目标"
    return compact if len(compact) <= max_length else compact[:max_length] + "…"


def create_task(
    db: Session, *, user_id: int, goal: str, document_ids: Optional[List[int]]
) -> AgentTask:
    task = AgentTask(
        user_id=user_id,
        title=build_title(goal),
        goal=goal.strip(),
        status=AGENT_TASK_STATUS_PENDING,
        scope_document_ids=document_ids,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, *, user_id: int, limit: int = 50) -> List[AgentTask]:
    stmt = (
        select(AgentTask)
        .where(AgentTask.user_id == user_id)
        .order_by(AgentTask.created_at.desc(), AgentTask.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_task_for_user(db: Session, *, task_id: int, user_id: int) -> Optional[AgentTask]:
    stmt = select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def delete_task(db: Session, *, task_id: int, user_id: int) -> bool:
    task = get_task_for_user(db, task_id=task_id, user_id=user_id)
    if task is None:
        return False
    db.delete(task)
    db.commit()
    return True


def reset_for_retry(db: Session, *, task: AgentTask) -> AgentTask:
    """把失败任务恢复为待执行，清空上次的产出与步骤。"""
    for step in list(task.steps):
        db.delete(step)
    task.status = AGENT_TASK_STATUS_PENDING
    task.result_markdown = None
    task.error_message = None
    task.prompt_tokens = 0
    task.completion_tokens = 0
    task.cost_cny = 0.0
    task.started_at = None
    task.finished_at = None
    db.commit()
    db.refresh(task)
    return task


def _ensure_budget(db: Session, user_id: int) -> None:
    budget = check_budget(db, user_id)
    if not budget.allowed:
        raise AgentTaskError(budget_reject_message(budget))


def _load_scope_documents(db: Session, task: AgentTask) -> List[Document]:
    stmt = select(Document).where(
        Document.owner_id == task.user_id,
        Document.status == DOCUMENT_STATUS_READY,
    )
    if task.scope_document_ids is not None:
        stmt = stmt.where(Document.id.in_(task.scope_document_ids))
    return list(db.execute(stmt.order_by(Document.id)).scalars().all())


async def _collect_materials(
    db: Session, task: AgentTask, documents: List[Document]
) -> Tuple[str, List[str]]:
    """把文档摘要 + 目标相关片段拼成材料块，控制总长度。"""
    parts: List[str] = []
    sources = [document.filename for document in documents]
    listed_documents = documents[:10]

    parts.append(f"共 {len(documents)} 篇文档参与本次任务。")
    for index, document in enumerate(listed_documents, start=1):
        summary = (document.summary or document.content[:300]).strip().replace("\n", " ")
        parts.append(f"{index}. 《{document.filename}》概要：{summary}")
    if len(documents) > len(listed_documents):
        parts.append(f"（其余 {len(documents) - len(listed_documents)} 篇未列出摘要）")

    try:
        rag = RAGService(db)
        chunks = await rag.retrieve_relevant_chunks(
            query=task.goal,
            owner_id=task.user_id,
            top_k=6,
            document_ids=[document.id for document in documents],
        )
    except Exception as exc:
        logger.warning(f"Agent 任务检索失败，降级为仅使用摘要: {exc}")
        chunks = []

    if chunks:
        parts.append("相关原文片段：")
        for index, chunk in enumerate(chunks, 1):
            document = getattr(chunk, "document", None)
            filename = getattr(document, "filename", "")
            label = f"[片段 {index} · 来自《{filename}》]" if filename else f"[片段 {index}]"
            parts.append(f"{label}\n{chunk.content}")

    materials = "\n\n".join(parts)
    return materials[: settings.AGENT_TASK_MAX_INPUT_CHARS], sources


def _parse_outline(raw: str, max_sections: int) -> List[str]:
    sections: List[str] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        text = text.strip("#").strip()
        text = text.lstrip("-*· ").strip()
        # 去掉 "1." "1、" "（1）" 这类编号
        for prefix in ("（", "(", "["):
            if text.startswith(prefix):
                text = text[1:].lstrip("0123456789)）] ").strip()
        if text and len(text) <= 40 and text not in sections:
            sections.append(text)
    return sections[:max_sections] or list(FALLBACK_SECTIONS)


async def _call_llm(
    db: Session,
    task: AgentTask,
    step: AgentTaskStep,
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    log_prompt: str,
) -> str:
    _ensure_budget(db, task.user_id)

    user = db.get(User, task.user_id)
    info = get_llm_client(user)
    if not info.client.api_key:
        raise AgentTaskError("未配置可用的 LLM API Key，无法生成任务成果。")

    started_at = start_timer()
    response = await info.client.chat.completions.create(
        model=info.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
        # 生成型任务关闭思考：思维链按输出计费，且会挤占正文预算
        extra_body={"enable_thinking": False},
    )
    content = (response.choices[0].message.content or "").strip()
    if getattr(response.choices[0], "finish_reason", None) == "length":
        logger.warning(f"==> Agent 任务步骤 {step.id} 输出达到 max_tokens，可能被截断")
    prompt_tokens, completion_tokens, total_tokens = extract_usage(response)
    cost = estimate_cost_cny(db, info.model_name, prompt_tokens, completion_tokens)

    create_llm_call_log(
        db,
        user_id=task.user_id,
        endpoint="/agent-task",
        prompt=log_prompt[:4000],
        response=content,
        tool_calls=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=elapsed_ms(started_at),
        status="success",
        model_name=info.model_name,
        provider="agent_task",
    )

    task.prompt_tokens += prompt_tokens
    task.completion_tokens += completion_tokens
    task.cost_cny += cost
    step.prompt_tokens += prompt_tokens
    step.completion_tokens += completion_tokens
    step.cost_cny += cost
    db.commit()

    if task.prompt_tokens + task.completion_tokens > settings.AGENT_TASK_MAX_TOKENS:
        raise AgentTaskError(
            f"单任务 token 已超过上限 {settings.AGENT_TASK_MAX_TOKENS}，任务中止。"
        )
    return content


def _new_step(db: Session, task: AgentTask, name: str) -> AgentTaskStep:
    seq = len(task.steps) + 1
    step = AgentTaskStep(
        task_id=task.id,
        seq=seq,
        name=name,
        status=AGENT_STEP_STATUS_RUNNING,
        started_at=_now(),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def _finish_step(db: Session, step: AgentTaskStep, summary: str) -> None:
    step.status = AGENT_STEP_STATUS_SUCCEEDED
    step.summary = summary[:2000]
    step.finished_at = _now()
    db.commit()


def _fail_task(db: Session, task_id: int, message: str) -> None:
    db.rollback()
    task = db.get(AgentTask, task_id)
    if task is None:
        return
    task.status = AGENT_TASK_STATUS_FAILED
    task.error_message = message[:2000]
    task.finished_at = _now()
    for step in task.steps:
        if step.status == AGENT_STEP_STATUS_RUNNING:
            step.status = AGENT_STEP_STATUS_FAILED
            step.finished_at = _now()
    db.commit()


def _assemble_markdown(task: AgentTask, sources: List[str], sections: List[Tuple[str, str]]) -> str:
    parts = [
        f"# {task.title}",
        f"> 目标：{task.goal}",
        f"> 生成时间：{_now().strftime('%Y-%m-%d %H:%M')} UTC",
        f"> 材料来源：{'、'.join(sources) if sources else '（无）'}",
    ]
    for title, content in sections:
        body = content.strip()
        if not body.lstrip().startswith("#"):
            parts.append(f"## {title}")
        parts.append(body)
    parts.append("## 参考材料")
    parts.extend(f"- 《{name}》" for name in sources)
    return "\n\n".join(parts)


async def run_task(db: Session, task_id: int) -> None:
    """执行一个 Agent 任务。由 Celery worker 调用。"""
    task = db.get(AgentTask, task_id)
    if task is None:
        logger.warning(f"Agent 任务 {task_id} 不存在，跳过")
        return

    task.status = AGENT_TASK_STATUS_RUNNING
    task.started_at = _now()
    task.finished_at = None
    task.error_message = None
    db.commit()

    try:
        _ensure_budget(db, task.user_id)
        documents = _load_scope_documents(db, task)
        if not documents:
            raise AgentTaskError(
                "知识库中没有可用的已就绪文档。请先上传资料并等待处理完成，再执行任务。"
            )

        step = _new_step(db, task, "retrieve")
        materials, sources = await _collect_materials(db, task, documents)
        if not materials.strip():
            raise AgentTaskError("未能从所选文档中提取到可用内容。")
        _finish_step(db, step, f"从 {len(documents)} 篇文档收集材料（{len(materials)} 字）")

        step = _new_step(db, task, "outline")
        raw_outline = await _call_llm(
            db,
            task,
            step,
            system_prompt=(
                "你是研究助理。只输出报告大纲，每行一个二级标题，不要编号、不要解释。"
                "必须覆盖目标中明确要求的所有部分；目标未要求时不要额外增加概览或引言。"
            ),
            user_prompt=(
                f"报告目标：{task.goal}\n\n"
                f"可用材料：\n{materials}\n\n"
                f"请给出 3~{settings.AGENT_TASK_MAX_SECTIONS} 个二级标题。"
            ),
            max_tokens=300,
            log_prompt=f"[大纲] {task.goal}",
        )
        outline = _parse_outline(raw_outline, settings.AGENT_TASK_MAX_SECTIONS)
        _finish_step(db, step, "大纲：" + " / ".join(outline))

        written: List[Tuple[str, str]] = []
        for section in outline:
            step = _new_step(db, task, "write")
            content = await _call_llm(
                db,
                task,
                step,
                system_prompt=(
                    "你是研究助理。只依据给定材料撰写报告的某一节，不得编造材料中没有的内容；"
                    "材料未覆盖的部分请明确写「资料未覆盖」。输出 Markdown 正文。"
                    "涉及数量、频次、比例等统计时，只统计材料中明确写出的条目并注明依据；"
                    "材料不足以精确统计时不要给出具体数字，改用定性描述。"
                    "文档篇数以材料首行「共 N 篇文档」为准。"
                ),
                user_prompt=(
                    f"报告目标：{task.goal}\n\n"
                    f"完整大纲：{' / '.join(outline)}\n\n"
                    f"当前小节：{section}\n\n"
                    f"材料：\n{materials}\n\n"
                    "请只输出这一节的正文，不要重复标题，也不要写其他小节。"
                ),
                max_tokens=settings.AGENT_TASK_SECTION_MAX_TOKENS,
                log_prompt=f"[撰写] {section}",
            )
            written.append((section, content))
            _finish_step(db, step, f"撰写「{section}」（{len(content)} 字）")

        step = _new_step(db, task, "finalize")
        task.result_markdown = _assemble_markdown(task, sources, written)
        _finish_step(db, step, f"汇总完成，共 {len(written)} 节，{len(task.result_markdown)} 字")

        task.status = AGENT_TASK_STATUS_SUCCEEDED
        task.finished_at = _now()
        db.commit()
        logger.info(
            f"==> Agent 任务 {task.id} 完成：{len(written)} 节，"
            f"tokens={task.prompt_tokens + task.completion_tokens}，¥{task.cost_cny:.4f}"
        )
    except Exception as exc:
        logger.warning(f"Agent 任务 {task_id} 失败: {exc}")
        _fail_task(db, task_id, str(exc))


def run_task_sync(task_id: int) -> None:
    """Celery 任务入口（同步包装）。"""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        asyncio.run(run_task(db, task_id))
    finally:
        db.close()
