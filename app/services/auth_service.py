from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.core.security import verify_password
from app.core.logging import logger

from typing import Optional

class AuthService:
    """
    鉴权相关业务逻辑
    """
    
    @classmethod
    def authenticate_user(cls, db: Session, email: str, password: str) -> Optional[User]:
        """
        验证用户邮箱和密码
        验证成功返回 User 对象，失败返回 None
        """
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            logger.warning(f"Authentication failed: User with email {email} not found")
            return None
            
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Authentication failed: Incorrect password for email {email}")
            return None
            
        return user
