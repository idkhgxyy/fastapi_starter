import httpx
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.db.session import engine
from app.utils.rate_limit import redis_client

router = APIRouter()


async def _check_database() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "up"}
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {"status": "down", "error": str(e)}


async def _check_redis() -> dict:
    try:
        await redis_client.ping()
        return {"status": "up"}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return {"status": "down", "error": str(e)}


async def _check_ollama() -> dict:
    base_url = settings.OLLAMA_BASE_URL.rstrip("/v1").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                return {
                    "status": "up",
                    "models": [m["name"] for m in resp.json().get("models", [])],
                }
            return {"status": "down", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
        return {"status": "down", "error": str(e)}


@router.get("/", summary="健康检查", tags=["Health"])
async def health_check():
    db_status = await _check_database()
    redis_status = await _check_redis()
    ollama_status = await _check_ollama()

    all_required_up = db_status["status"] == "up" and redis_status["status"] == "up"
    http_status = status.HTTP_200_OK if all_required_up else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        content={
            "status": "ok" if all_required_up else "degraded",
            "version": settings.VERSION,
            "dependencies": {
                "database": db_status,
                "redis": redis_status,
                "ollama": ollama_status,
            },
        },
        status_code=http_status,
    )
