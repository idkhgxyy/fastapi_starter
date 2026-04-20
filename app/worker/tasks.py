import time
from app.worker.celery_app import celery_app
from app.core.logging import logger

@celery_app.task(name="process_document_task", bind=True)
def process_document_task(self, document_id: int):
    """
    模拟一个极其耗时的任务（比如处理文档切分、向量化入库）
    """
    logger.info(f"==> 🚀 开始处理文档，文档 ID: {document_id}")
    
    # 模拟分步处理过程
    steps = ["下载文档...", "提取文本内容...", "调用 LLM 进行总结...", "切片并向量化...", "写入向量数据库..."]
    
    for i, step in enumerate(steps):
        logger.info(f"[文档 {document_id}] 步骤 {i+1}/5: {step}")
        # 可以通过 update_state 将进度实时同步回 Redis
        self.update_state(state="PROGRESS", meta={"step": step, "current": i+1, "total": 5})
        time.sleep(3)  # 模拟每一步耗时 3 秒钟
        
    logger.info(f"==> ✅ 文档 {document_id} 处理完成！")
    
    # 最终的返回值，也是保存在 Redis 中的 task result
    return {
        "document_id": document_id,
        "status": "success",
        "message": "文档解析与向量化已完成"
    }