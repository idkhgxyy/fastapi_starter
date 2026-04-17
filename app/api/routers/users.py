from fastapi import APIRouter, status, Depends
from typing import List
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserOut
from app.services.user_service import UserService
from app.api.deps import get_db, get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="创建用户")
async def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    通过 Depends(get_db) 自动获取数据库连接，并传递给 service 层
    """
    return UserService.create_user(db, user_in)

@router.get("/me", response_model=UserOut, summary="获取当前登录用户信息")
async def get_user_me(current_user: User = Depends(get_current_user)):
    """
    这是一个受保护的接口。
    必须在请求头带上有效的 Authorization: Bearer <Token> 才能访问。
    """
    return current_user

@router.get("/{user_id}", response_model=UserOut, summary="获取指定用户详情")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    return UserService.get_user(db, user_id)

@router.get("/", response_model=List[UserOut], summary="获取所有用户列表")
async def list_users(db: Session = Depends(get_db)):
    return UserService.list_users(db)
