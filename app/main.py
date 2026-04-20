from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routers import health, users, auth, chat, tasks, worker, rag, observability
from app.utils.errors import AppException, app_exception_handler
from app.core.logging import logger
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.models.user import User
from app.api.middleware import RequestIDMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器
    """
    # --- 启动时执行 ---
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")
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
    lifespan=lifespan,
    docs_url=None  # 我们将接管默认的 docs 路由
)

# 注册中间件
app.add_middleware(RequestIDMiddleware)

# 初始化并注册 Prometheus 指标暴露器
Instrumentator().instrument(app).expose(app)

# 自定义 Swagger UI 路由，添加深色模式适配
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    html_content = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    ).body.decode("utf-8")
    
    # 注入 CSS 样式，使 Swagger UI 在系统深色模式下表现良好，同时保留浅色模式
    custom_css = """
    <style>
        @media (prefers-color-scheme: dark) {
            body { background-color: #121212 !important; color: #e0e0e0 !important; }
            
            /* 顶部栏和基础布局 */
            .swagger-ui .topbar { background-color: #1e1e1e !important; border-bottom: 1px solid #333; }
            .swagger-ui .info .title, .swagger-ui .info p, .swagger-ui .info li { color: #e0e0e0 !important; }
            .swagger-ui .scheme-container { background-color: #1e1e1e !important; border-bottom: 1px solid #333; box-shadow: none; }
            
            /* 模块和操作块 */
            .swagger-ui .opblock { border-color: #333 !important; background-color: rgba(255,255,255,0.02); }
            .swagger-ui .opblock-summary-control { outline: none; }
            .swagger-ui .opblock .opblock-summary-operation-id, 
            .swagger-ui .opblock .opblock-summary-path, 
            .swagger-ui .opblock .opblock-summary-path__deprecated { color: #e0e0e0 !important; }
            .swagger-ui .opblock-description-wrapper p { color: #b0b0b0 !important; }
            
            /* 弹窗 (Modal) 和 Auth 界面 */
            .swagger-ui .dialog-ux .modal-ux { background-color: #1e1e1e !important; border: 1px solid #444 !important; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            .swagger-ui .dialog-ux .modal-ux-header { border-bottom: 1px solid #444 !important; }
            .swagger-ui .dialog-ux .modal-ux-header h3, 
            .swagger-ui .dialog-ux .modal-ux-content h4, 
            .swagger-ui .dialog-ux .modal-ux-content p { color: #e0e0e0 !important; }
            .swagger-ui .auth-container { border-bottom-color: #444 !important; }
            
            /* 表单元素 */
            .swagger-ui input[type=text], .swagger-ui input[type=password], .swagger-ui textarea, .swagger-ui select {
                background-color: #2d2d2d !important;
                color: #fff !important;
                border: 1px solid #555 !important;
            }
            .swagger-ui input[type=text]:focus, .swagger-ui input[type=password]:focus, .swagger-ui textarea:focus {
                border-color: #49cc90 !important;
            }
            
            /* 按钮 */
            .swagger-ui .btn { color: #e0e0e0; border-color: #666; background: transparent; }
            .swagger-ui .btn.authorize { color: #49cc90 !important; border-color: #49cc90 !important; }
            .swagger-ui .btn.execute { background-color: #49cc90 !important; color: #fff !important; border-color: #49cc90 !important; }
            .swagger-ui .btn.cancel { border-color: #f93e3e !important; color: #f93e3e !important; }
            .swagger-ui .btn-done { color: #fff !important; }
            
            /* 表格和参数 */
            .swagger-ui table thead tr td, .swagger-ui table thead tr th { border-bottom-color: #444 !important; color: #e0e0e0 !important; }
            .swagger-ui .parameter__name, .swagger-ui .parameter__type { color: #e0e0e0 !important; }
            .swagger-ui .response-col_status, .swagger-ui .response-col_description { color: #e0e0e0 !important; }
            .swagger-ui table.model tbody tr td { border-bottom-color: #333 !important; }
            
            /* 响应体高亮块 */
            .swagger-ui .highlight-code { background-color: #2d2d2d !important; }
            .swagger-ui .model-box { background-color: #2d2d2d !important; }
            .swagger-ui .model { color: #e0e0e0 !important; }
            .swagger-ui .prop-type { color: #8aafff !important; }
            
            /* 解决 Auth 错误文本颜色不可见问题 */
            .swagger-ui .auth-container .errors { background-color: #401010 !important; color: #ff6060 !important; }
            .swagger-ui .dialog-ux .modal-ux-header .close-modal { fill: #e0e0e0 !important; }
            .swagger-ui svg { fill: #e0e0e0; }
            .swagger-ui .btn.authorize svg { fill: #49cc90 !important; }
        }
    </style>
    """
    html_content = html_content.replace("</head>", f"{custom_css}</head>")
    return HTMLResponse(html_content)

# 注册全局异常处理器
app.add_exception_handler(AppException, app_exception_handler)

# 注册所有路由
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(worker.router, prefix="/api/worker", tags=["Worker (Async)"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])
app.include_router(observability.router, prefix="/api/observability", tags=["Observability"])

@app.get("/", summary="根目录重定向或欢迎信息", tags=["Root"])
async def root():
    logger.info("Root endpoint accessed.")
    return {
        "message": "Welcome to FastAPI Starter. Visit /docs for API documentation.",
        "docs_url": "/docs"
    }
