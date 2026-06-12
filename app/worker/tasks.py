import asyncio

from app.core.logging import logger
from app.db.session import SessionLocal
from app.services.rag_service import RAGService
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
