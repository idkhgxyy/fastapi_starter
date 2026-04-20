from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TaskBase(BaseModel):
    title: str = Field(..., description="任务标题", max_length=255)
    description: Optional[str] = Field(None, description="任务详细描述")
    status: str = Field("pending", description="任务状态：pending, in_progress, completed")

class TaskCreate(TaskBase):
    """
    创建任务时的请求模型
    """
    pass

class TaskUpdate(BaseModel):
    """
    更新任务时的请求模型，允许部分更新
    """
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None

class TaskOut(TaskBase):
    """
    返回给前端的任务响应模型
    """
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True
