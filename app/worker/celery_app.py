from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# 实例化 Celery 应用
# 第一个参数是 name，broker 和 backend 我们都用同一个 Redis
celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

# Celery 基础配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # 定时任务按北京时间解释 crontab（阿里云百炼闲时窗口为北京时间 22:00~次日 8:00）
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 如果希望任务在一定时间后自动释放，可以配置结果过期时间（例如 1 天）
    result_expires=86400,
    # 闲时批量任务：每天 22:30（北京时间）为无摘要文档生成摘要，
    # 全程落在百炼闲时窗口（22:00~次日 8:00），LLM 单价为忙时的一半
    beat_schedule={
        "summarize-pending-documents-off-peak": {
            "task": "app.worker.tasks.summarize_pending_documents",
            "schedule": crontab(hour=22, minute=30),
        },
    },
)

# 自动发现 tasks.py 文件里的任务，目前我们需要手动写死我们等下要建的 tasks 模块
celery_app.autodiscover_tasks(["app.worker.tasks"])
