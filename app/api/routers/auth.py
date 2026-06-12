from datetime import timedelta

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.schemas.auth import SetupRequest, SetupStatus, Token
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.utils.errors import AppException

router = APIRouter()


@router.get("/setup/status", response_model=SetupStatus, summary="检查系统初始化状态")
async def get_setup_status(db: Session = Depends(get_db)):
    """检测系统是否已完成初始化（是否已有用户）"""
    user_count = db.execute(select(func.count(User.id))).scalar()
    return SetupStatus(
        initialized=user_count > 0,
        llm_mock=settings.LLM_MOCK,
        llm_provider=settings.LLM_PROVIDER,
    )


@router.post("/setup", response_model=Token, summary="首次初始化：创建管理员并登录")
async def initial_setup(
    setup_in: SetupRequest,
    db: Session = Depends(get_db),
):
    """
    仅在系统未初始化时可用（无用户存在时）。
    创建第一个用户并直接返回 JWT Token。
    """
    user_count = db.execute(select(func.count(User.id))).scalar()
    if user_count > 0:
        raise AppException(
            code=1010, msg="System already initialized", status_code=status.HTTP_400_BAD_REQUEST
        )

    user_in = type("UserCreate", (), {
        "username": setup_in.username,
        "email": setup_in.email,
        "password": setup_in.password,
        "full_name": setup_in.full_name or setup_in.username,
    })()

    user = UserService.create_user(db, user_in)

    # 如果提供了 LLM API Key，同时配置
    if setup_in.llm_api_key:
        from app.schemas.user import UserLLMConfigUpdate
        UserService.update_llm_config(db, user.id, UserLLMConfigUpdate(
            llm_provider=setup_in.llm_provider or settings.LLM_PROVIDER,
            llm_base_url=setup_in.llm_base_url or settings.LLM_BASE_URL,
            llm_model_name=setup_in.llm_model_name or settings.LLM_MODEL_NAME,
            llm_api_key=setup_in.llm_api_key,
        ))

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token, summary="用户登录并获取 Token")
async def login_access_token(
    db: Session = Depends(get_db),
    # OAuth2PasswordRequestForm 默认接收 x-www-form-urlencoded 格式的数据（即 username 和 password）
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 兼容的 token 登录接口，通过用户名（或邮箱）和密码获取 JWT token。
    注意：在我们的设计里，这里的 form_data.username 实际上前端传的是 email。
    """
    user = AuthService.authenticate_user(db, email=form_data.username, password=form_data.password)

    if not user:
        raise AppException(
            code=1005, msg="Incorrect email or password", status_code=status.HTTP_401_UNAUTHORIZED
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 按照 JWT 标准，"sub" (subject) 存放用户的唯一标识符
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
