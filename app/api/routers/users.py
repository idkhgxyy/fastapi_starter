from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_superuser, get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.user import (
    PasswordUpdate,
    UserBudgetOut,
    UserBudgetUpdate,
    UserCreate,
    UserLLMConfigUpdate,
    UserOut,
)
from app.services.cost_guard import check_budget
from app.services.user_service import UserService
from app.utils.rate_limit import RateLimiter

router = APIRouter()

# 注册接口限流：同一 IP 每小时最多 5 次注册（测试环境不限流）
register_limiter = RateLimiter(times=5, seconds=3600) if not settings.TESTING else None


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="创建用户")
async def create_user(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    """
    通过 Depends(get_db) 自动获取数据库连接，并传递给 service 层。
    限流：同一 IP 每小时最多 5 次注册请求。
    """
    if register_limiter:
        await register_limiter(request)
    return UserService.create_user(db, user_in)


@router.get("/me", response_model=UserOut, summary="获取当前登录用户信息")
async def get_user_me(current_user: User = Depends(get_current_user)):
    """
    这是一个受保护的接口。
    必须在请求头带上有效的 Authorization: Bearer <Token> 才能访问。
    """
    return current_user


@router.put("/me/llm-config", response_model=UserOut, summary="更新当前用户的 LLM 配置")
async def update_user_llm_config(
    config_in: UserLLMConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新用户自己的大模型服务商配置 (支持多租户独立配置)。
    API Key 将会被对称加密后入库，确保安全性。
    """
    return UserService.update_llm_config(db, current_user.id, config_in)


@router.put("/me/password", response_model=UserOut, summary="修改当前用户密码")
async def change_password(
    password_in: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UserService.change_password(db, current_user.id, password_in)


@router.get("/me/budget", response_model=UserBudgetOut, summary="查看当前用户的成本预算与用量")
async def get_my_budget(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回生效预算（个人优先，回退全局）与当前周期内花费/剩余"""
    status = check_budget(db, current_user.id)
    return UserBudgetOut(
        budget_cny=status.budget_cny,
        budget_period=status.period,
        has_personal_budget=current_user.budget_cny is not None,
        spent_cny=status.spent_cny,
        remaining_cny=status.remaining_cny,
        period_start=status.period_start.isoformat() if status.period_start else None,
    )


@router.put("/me/budget", response_model=UserBudgetOut, summary="设置当前用户的成本预算")
async def update_my_budget(
    budget_in: UserBudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设置个人预算（元/周期）。budget_cny 置 null 回退全局默认，<=0 关闭熔断"""
    if budget_in.budget_period not in ("monthly", None):
        raise HTTPException(status_code=400, detail="budget_period 目前仅支持 monthly")

    current_user.budget_cny = budget_in.budget_cny
    if budget_in.budget_period:
        current_user.budget_period = budget_in.budget_period
    db.commit()
    db.refresh(current_user)
    return await get_my_budget(db=db, current_user=current_user)


@router.get("/{user_id}", response_model=UserOut, summary="获取指定用户详情")
async def get_user(
    user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return UserService.get_user(db, user_id)


@router.get("/", response_model=List[UserOut], summary="获取所有用户列表")
async def list_users(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)
):
    """
    需要超级管理员权限才能访问
    """
    return UserService.list_users(db)


@router.delete("/{user_id}", response_model=UserOut, summary="删除指定用户")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """
    需要超级管理员权限才能删除用户
    """
    return UserService.delete_user(db, user_id)
