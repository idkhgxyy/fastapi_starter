from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from typing import Optional
from app.models.user import User
from app.api.deps import get_current_user

# 导入我们刚刚写的 Celery 任务
from app.worker.tasks import process_document_task
from app.worker.celery_app import celery_app

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
    current_user: User = Depends(get_current_user)
):
    """
    提交一个极度耗时的文档处理任务（例如切分、向量化入库等）。
    API 会立即返回，不会阻塞，后台 Celery 会慢慢执行。
    """
    # 异步触发 Celery 任务
    task = process_document_task.delay(request.document_id)
    
    return TaskStatusResponse(
        task_id=task.id,
        status=task.status,
        result={"message": "任务已提交至后台队列，请稍后查询进度。"}
    )

@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="查询异步任务执行状态")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    根据 Task ID 去 Redis 查询该任务当前的状态与进度
    """
    # AsyncResult 可以直接通过 ID 去 Redis 拿结果
    task_result = celery_app.AsyncResult(task_id)
    
    response = TaskStatusResponse(
        task_id=task_id,
        status=task_result.status
    )
    
    # 检查任务是否成功完成
    if task_result.status == "SUCCESS":
        response.result = task_result.result
    # 检查任务是否失败
    elif task_result.status == "FAILURE":
        response.result = {"error": str(task_result.info)}
    # 检查是否还在处理中，获取我们通过 update_state 更新的 meta 信息
    elif task_result.status == "PROGRESS":
        response.result = task_result.info
    
    return response