from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.errors import AppException
from fastapi import status

class TaskService:
    @staticmethod
    def create_task(db: Session, task_in: TaskCreate, owner_id: int) -> Task:
        """
        创建新任务
        """
        new_task = Task(
            title=task_in.title,
            description=task_in.description,
            status=task_in.status,
            owner_id=owner_id
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        return new_task

    @staticmethod
    def list_tasks(db: Session, owner_id: int, skip: int = 0, limit: int = 100):
        """
        获取当前用户的所有任务列表
        """
        return db.execute(
            select(Task)
            .where(Task.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .order_by(Task.created_at.desc())
        ).scalars().all()

    @staticmethod
    def get_task(db: Session, task_id: int, owner_id: int) -> Task:
        """
        获取单个任务详情
        """
        task = db.execute(
            select(Task).where(Task.id == task_id, Task.owner_id == owner_id)
        ).scalar_one_or_none()
        
        if not task:
            raise AppException(code=1004, msg="Task not found", status_code=status.HTTP_404_NOT_FOUND)
        return task

    @staticmethod
    def update_task(db: Session, task_id: int, owner_id: int, task_in: TaskUpdate) -> Task:
        """
        更新任务信息
        """
        task = TaskService.get_task(db, task_id, owner_id)
        
        # 只更新传入的非空字段
        update_data = task_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(task, key, value)
            
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def delete_task(db: Session, task_id: int, owner_id: int) -> Task:
        """
        删除任务
        """
        task = TaskService.get_task(db, task_id, owner_id)
        db.delete(task)
        db.commit()
        return task
