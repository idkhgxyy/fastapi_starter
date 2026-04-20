import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 声明一个上下文变量，用于保存当前请求的 request_id
request_id_context_var: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    为每个请求生成并注入唯一 Request ID 的中间件
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        # 生成一个唯一的 UUID 作为 request_id
        request_id = str(uuid.uuid4())
        
        # 将 request_id 设置到上下文中
        token = request_id_context_var.set(request_id)
        
        try:
            # 将 request_id 绑定到 request 的 state 里，方便在路由中直接获取
            request.state.request_id = request_id
            
            # 继续处理请求
            response = await call_next(request)
            
            # 在响应头中带上 X-Request-ID，方便客户端排查问题
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 清理上下文变量
            request_id_context_var.reset(token)
