from typing import Any, Optional

from fastapi import Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse


class AppException(Exception):
    """
    自定义业务异常类
    用于统一抛出业务错误，后续会被全局异常处理器捕获
    """

    def __init__(
        self,
        code: int,
        msg: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data: Optional[Any] = None,
    ):
        self.code = code
        self.msg = msg
        self.status_code = status_code
        self.data = data


async def app_exception_handler(request: Request, exc: AppException):
    """
    全局业务异常处理函数
    将异常转换为统一格式的 JSON 响应: {"code": ..., "msg": ..., "data": ...}
    """
    return JSONResponse(
        status_code=exc.status_code, content={"code": exc.code, "msg": exc.msg, "data": exc.data}
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    将 FastAPI 内置 HTTPException 转换为统一格式
    解决 OAuth2 等中间件抛出的 401/403 错误格式不统一问题
    """
    code_map = {
        401: 1008,
        403: 1009,
        404: 1001,
        429: 1029,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code_map.get(exc.status_code, exc.status_code),
            "msg": str(exc.detail),
            "data": None,
        },
    )
