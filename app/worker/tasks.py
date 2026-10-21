import asyncio

from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.services.rag_service import RAGService
from app.services.semantic_cache import invalidate_user_cache
from app.worker.celery_app import celery_app


@celery_app.task(
    name="process_document_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
)
def process_document_task(self, document_id: int):
    """
    对已上传文档执行真实的切分、Embedding 和入库流程。
    遇到临时故障（如 Ollama 未就绪）会自动重试最多 3 次，指数退避。
    """
    logger.info(
        f"==> 开始异步处理文档，文档 ID: {document_id} (attempt {self.request.retries + 1})"
    )
    db = SessionLocal()
    rag_service = RAGService(db)

    try:
        self.update_state(
            state="PROGRESS",
            meta={"step": "processing_document", "current": 1, "total": 1},
        )
        document = asyncio.run(
            rag_service.process_document(
                document_id=document_id,
                task_id=self.request.id,
            )
        )
        logger.info(f"==> 文档处理完成，文档 ID: {document_id}, chunks: {document.chunks_count}")
        return {
            "document_id": document.id,
            "status": document.status,
            "chunks_count": document.chunks_count,
            "message": "文档切分与向量化已完成",
        }
    except Exception as exc:
        db.rollback()
        rag_service.mark_document_failed(
            document_id=document_id,
            error_message=str(exc),
            task_id=self.request.id,
        )
        logger.error(f"==> 文档处理失败，文档 ID: {document_id}, error: {exc}")
        raise
    finally:
        db.close()


async def _summarize_document(db, document) -> str:
    """为单个文档生成摘要：优先用户 BYOK 云端模型，云端不可用降级本地 Ollama"""
    from app.models.user import User
    from app.services.llm_observability_service import (
        create_llm_call_log,
        extract_usage,
    )
    from app.services.llm_service import _build_fallback_info, get_llm_client

    user = db.get(User, document.owner_id) if document.owner_id else None
    info = get_llm_client(user)
    provider = (user.llm_provider if user else None) or "summarize"
    if not info.client.api_key:
        info = _build_fallback_info()
        provider = "ollama"
        if info is None:
            raise RuntimeError("无可用 LLM（未配置 Key 且无本地降级）")

    content = document.content[: settings.SUMMARY_MAX_INPUT_CHARS]
    response = await info.client.chat.completions.create(
        model=info.model_name,
        messages=[
            {
                "role": "system",
                "content": "你是文档摘要助手。请基于给定文档内容生成不超过 200 字的中文摘要，"
                "概括文档的主题与关键信息，不要编造文档中不存在的内容。",
            },
            {
                "role": "user",
                "content": f"文档《{document.filename}》内容如下：\n\n{content}",
            },
        ],
        temperature=0.3,
        max_tokens=1024,
        # 批量摘要不需要思考：思考会吃掉输出预算且按输出价计费，
        # 关掉后正文有保障、成本减半（deepseek-v4 系混合思考模型）
        extra_body={"enable_thinking": False},
    )
    summary = response.choices[0].message.content

    # 记账：闲时调用同样按定价中心折算（闲时实际扣费为忙时的一半，
    # 我们按忙时价保守记账，账面只多不少）
    prompt_tokens, completion_tokens, total_tokens = extract_usage(response)
    create_llm_call_log(
        db,
        user_id=document.owner_id,
        endpoint="/worker/summarize",
        prompt=f"[闲时摘要] {document.filename}",
        response=summary,
        tool_calls=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=0.0,
        status="success",
        model_name=info.model_name,
        provider=provider,
    )
    return summary


def _persist_summary(db, document, summary: str) -> None:
    """落库摘要，并失效该用户的语义缓存。

    摘要会进入检索上下文（全局性问题的兜底资料），"从无到有"意味着知识库可用
    信息变了：摘要生成之前缓存的回答可能完全没看到这篇文档的概览，必须作废。
    """
    document.summary = summary
    db.commit()
    invalidate_user_cache(db, document.owner_id)


@celery_app.task(name="app.worker.tasks.summarize_pending_documents")
def summarize_pending_documents():
    """
    闲时批量任务（Celery beat：每天 22:30 北京时间）：
    为还没有摘要的已就绪文档生成摘要。

    阿里云百炼的闲时窗口为北京时间 22:00~次日 8:00，LLM 单价为忙时的一半，
    把不紧急的批量生成任务调度到该窗口内执行是纯成本优化。
    """
    from app.models.document import DOCUMENT_STATUS_READY, Document

    logger.info("==> [闲时摘要] 开始扫描待摘要文档")
    db = SessionLocal()
    try:
        documents = (
            db.query(Document)
            .filter(
                Document.status == DOCUMENT_STATUS_READY,
                Document.summary.is_(None),
            )
            .limit(settings.SUMMARIZE_MAX_DOCS_PER_RUN)
            .all()
        )
        if not documents:
            logger.info("==> [闲时摘要] 没有待摘要文档")
            return {"summarized": 0, "failed": 0}

        summarized, failed = 0, 0
        for document in documents:
            try:
                summary = asyncio.run(_summarize_document(db, document))
                _persist_summary(db, document, summary)
                summarized += 1
                logger.info(f"==> [闲时摘要] 文档 {document.id} 摘要完成 ({len(summary)} 字)")
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.warning(f"==> [闲时摘要] 文档 {document.id} 摘要失败: {exc}")

        logger.info(f"==> [闲时摘要] 本轮完成: 成功 {summarized} / 失败 {failed}")
        return {"summarized": summarized, "failed": failed}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.run_agent_task")
def run_agent_task_task(task_id: int):
    """执行目标型 Agent 任务（固定流水线，详见 agent_task_service）。"""
    logger.info(f"==> 开始执行 Agent 任务 {task_id}")
    from app.services.agent_task_service import run_task_sync

    run_task_sync(task_id)
