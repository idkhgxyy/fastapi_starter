import logging
import sys

def setup_logging():
    """
    初始化日志配置
    """
    logger = logging.getLogger("fastapi_starter")
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# 导出配置好的全局 logger
logger = setup_logging()
