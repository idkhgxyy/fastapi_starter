from fastapi import APIRouter, status
from typing import List
from app.schemas.user import UserCreate, UserOut
from app.services.user_service import UserService

router = APIRouter()

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="创建用户")
async def create_user(user_in: UserCreate):
    """
    路由层只做“接参数 + 调用service + 返回”
    """
    return UserService.create_user(user_in)

@router.get("/{user_id}", response_model=UserOut, summary="获取指定用户详情")
async def get_user(user_id: int):
    return UserService.get_user(user_id)

@router.get("/", response_model=List[UserOut], summary="获取所有用户列表")
async def list_users():
    return UserService.list_users()
