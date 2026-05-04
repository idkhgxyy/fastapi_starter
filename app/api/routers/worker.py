from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.rag_service import RAGService
from app.worker.celery_app import celery_app
from app.worker.tasks import process_document_task

router = APIRouter()

class DocumentProcessRequest(BaseModel):
    document_id: int

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None

@router.post("/process", response_model=TaskStatusResponse, summary="提交一个处理文档的异步任务")
async def trigger_document_processing(
    request: DocumentProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    为当前用户的指定文档重新提交一次异步处理任务。
    """
    rag_service = RAGService(db)
    document = rag_service.get_document_for_user(
        document_id=request.document_id,
        owner_id=current_user.id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    task = process_document_task.delay(request.document_id)
    document = rag_service.requeue_document(
        document_id=request.document_id,
        owner_id=current_user.id,
        task_id=task.id,
    )

    return TaskStatusResponse(
        task_id=task.id,
        status=document.status,
        result={
            "document_id": document.id,
            "message": "文档已重新提交至后台队列，请稍后查询进度。",
        },
    )

@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="查询异步任务执行状态")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据 Task ID 查询当前用户文档处理任务的执行状态。
    """
    rag_service = RAGService(db)
    document = rag_service.get_document_by_task_id_for_user(
        task_id=task_id,
        owner_id=current_user.id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    task_result = celery_app.AsyncResult(task_id)
    
    response = TaskStatusResponse(
        task_id=task_id,
        status=task_result.status
    )
    
    if task_result.status == "SUCCESS":
        response.result = task_result.result
    elif task_result.status == "FAILURE":
        response.result = {"error": str(task_result.info)}
    elif task_result.status == "PROGRESS":
        response.result = task_result.info
    else:
        response.result = {
            "document_id": document.id,
            "document_status": document.status,
        }
    
    return response
