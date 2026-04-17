from datetime import timedelta
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.auth import Token
from app.services.auth_service import AuthService
from app.core.security import create_access_token
from app.core.config import settings
from app.utils.errors import AppException

router = APIRouter()

@router.post("/login", response_model=Token, summary="用户登录并获取 Token")
async def login_access_token(
    db: Session = Depends(get_db),
    # OAuth2PasswordRequestForm 默认接收 x-www-form-urlencoded 格式的数据（即 username 和 password）
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 兼容的 token 登录接口，通过用户名（或邮箱）和密码获取 JWT token。
    注意：在我们的设计里，这里的 form_data.username 实际上前端传的是 email。
    """
    user = AuthService.authenticate_user(db, email=form_data.username, password=form_data.password)
    
    if not user:
        raise AppException(
            code=1005,
            msg="Incorrect email or password",
            status_code=status.HTTP_401_UNAUTHORIZED
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 按照 JWT 标准，"sub" (subject) 存放用户的唯一标识符
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
