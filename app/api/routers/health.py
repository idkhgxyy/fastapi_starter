from fastapi import APIRouter

router = APIRouter()

@router.get("/health", summary="健康检查", tags=["Health"])
async def health_check():
    """
    检查系统健康状态。
    返回 {"ok": True} 代表服务正常运行。
    """
    return {"ok": True}
