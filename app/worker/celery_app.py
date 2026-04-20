import os
from celery import Celery
from app.core.config import settings

# 实例化 Celery 应用
# 第一个参数是 name，broker 和 backend 我们都用同一个 Redis
celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Celery 基础配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # 如果希望任务在一定时间后自动释放，可以配置结果过期时间（例如 1 天）
    result_expires=86400,
)

# 自动发现 tasks.py 文件里的任务，目前我们需要手动写死我们等下要建的 tasks 模块
celery_app.autodiscover_tasks(["app.worker.tasks"])