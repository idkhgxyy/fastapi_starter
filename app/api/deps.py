from typing import Generator
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db.session import SessionLocal
from app.core.security import SECRET_KEY, ALGORITHM
from app.schemas.auth import TokenPayload
from app.models.user import User
from app.utils.errors import AppException

# OAuth2 配置，指明了客户端应该去哪个 URL 换取 Token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
