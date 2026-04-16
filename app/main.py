from fastapi import FastAPI
from app.api.routers import health

app = FastAPI(
    title="FastAPI Starter",
    description="A production-ready FastAPI starter project.",
    version="0.1.0"
)

# 注册健康检查路由
app.include_router(health.router, prefix="/api")

@app.get("/", summary="根目录重定向或欢迎信息", tags=["Root"])
async def root():
    return {
        "message": "Welcome to FastAPI Starter. Visit /docs for API documentation.",
        "docs_url": "/docs"
    }
