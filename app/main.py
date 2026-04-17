from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.api.routers import health, users
from app.utils.errors import AppException, app_exception_handler
from app.core.logging import logger
from app.db.session import engine
from app.db.base import Base
from app.models.user import User  # 确保模型被导入，以便 create_all 能识别到它

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器
    """
    # --- 启动时执行 ---
    logger.info("Starting FastAPI application...")
    logger.info("Testing database connection...")
    try:
        # 测试与 PostgreSQL 的连接
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info(f"Database connection successful! (Test query returned: {result.scalar()})")
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # 这里只报 error 并不抛出异常（为了防止没有 DB 时整个项目起不来），生产中视情况可阻断启动。
    
    yield
    
    # --- 停止时执行 ---
    logger.info("Shutting down FastAPI application...")
    # 可在此处释放连接池等资源

app = FastAPI(
    title="FastAPI Starter",
    description="A production-ready FastAPI starter project.",
    version="0.1.0",
    lifespan=lifespan
)

# 注册全局异常处理器
app.add_exception_handler(AppException, app_exception_handler)

# 注册所有路由
app.include_router(health.router, prefix="/api")
app.include_router(users.router, prefix="/api/users", tags=["Users"])

@app.get("/", summary="根目录重定向或欢迎信息", tags=["Root"])
async def root():
    logger.info("Root endpoint accessed.")
    return {
        "message": "Welcome to FastAPI Starter. Visit /docs for API documentation.",
        "docs_url": "/docs"
    }
