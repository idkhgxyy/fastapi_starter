from typing import Generator
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db.session import SessionLocal
from app.core.config import settings
from app.schemas.auth import TokenPayload
from app.models.user import User
from app.utils.errors import AppException
import redis.asyncio as redis_async

# OAuth2 配置，指明了客户端应该去哪个 URL 换取 Token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

redis_client = None

async def get_redis() -> redis_async.Redis:
    global redis_client
    if redis_client is None:
        redis_client = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client

def get_db() -> Generator:
    """
    FastAPI 依赖注入：获取数据库 Session。
    每次请求时创建一个新的数据库 Session，请求结束时自动关闭。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """
    FastAPI 依赖注入：获取当前登录用户。
    1. 从请求头中提取 JWT Token
    2. 验证 Token 是否合法且未过期
    3. 解析出 User ID 并从数据库中查询返回 User 对象
    """
    try:
        # 解码 JWT
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)
    except (jwt.PyJWTError, ValidationError):
        raise AppException(
            code=1003,
            msg="Could not validate credentials (invalid or expired token)",
            status_code=status.HTTP_401_UNAUTHORIZED
        )
        
    if not token_data.sub:
        raise AppException(
            code=1003,
            msg="Invalid token payload",
            status_code=status.HTTP_401_UNAUTHORIZED
        )
        
    # 查询数据库中是否有该用户
    user = db.get(User, int(token_data.sub))
    if not user:
        raise AppException(
            code=1004,
            msg="User not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
        
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    检查当前用户是否被激活
    """
    if not current_user.is_active:
        raise AppException(
            code=1006,
            msg="Inactive user",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return current_user

def get_current_active_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    检查当前用户是否是超级管理员
    """
    if not current_user.is_superuser:
        raise AppException(
            code=1007,
            msg="The user doesn't have enough privileges",
            status_code=status.HTTP_403_FORBIDDEN
        )
    return current_user

class RateLimiter:
    """
    基于 Redis 的简单接口限流依赖
    """
    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds

    async def __call__(
        self, 
        current_user: User = Depends(get_current_user), 
        redis_client: redis_async.Redis = Depends(get_redis)
    ):
        key = f"rate_limit:user:{current_user.id}"
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, self.seconds)
        if current > self.times:
            raise AppException(
                code=1008,
                msg=f"请求过于频繁，请 {self.seconds} 秒后再试。",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return True
