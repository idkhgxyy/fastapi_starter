import logging
import sys

# 延迟导入以防循环依赖
def get_request_id():
    from app.api.middleware import request_id_context_var
    try:
        return request_id_context_var.get()
    except Exception:
        return "-"

class RequestIDFilter(logging.Filter):
    """自定义日志过滤器：给每一条日志附加 request_id 属性"""
    def filter(self, record):
        record.request_id = get_request_id()
        return True

def setup_logging():
    """
    初始化日志配置
    """
    logger = logging.getLogger("fastapi_starter")
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        
        # 增加 RequestIDFilter
        logger.addFilter(RequestIDFilter())
        handler.addFilter(RequestIDFilter())
        
        # 更新日志格式：增加 [%(request_id)s]
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [ReqID: %(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# 导出配置好的全局 logger
logger = setup_logging()
