from fastapi import APIRouter, HTTPException, status
from typing import List
from app.schemas.user import UserCreate, UserOut

router = APIRouter()

# --- 模拟内存数据库（在 Day 5 之前临时使用） ---
FAKE_DB = []
CURRENT_ID = 1
# -----------------------------------------------

@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="创建用户")
async def create_user(user_in: UserCreate):
    global CURRENT_ID
    
    # 模拟：检查邮箱是否已被注册
    for user in FAKE_DB:
        if user["email"] == user_in.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )
            
    # 模拟：将数据存入数据库（去除了密码哈希等复杂逻辑，只做演示）
    new_user = user_in.model_dump()
    new_user["id"] = CURRENT_ID
    new_user["is_active"] = True
    
    FAKE_DB.append(new_user)
    CURRENT_ID += 1
    
    return new_user

@router.get("/{user_id}", response_model=UserOut, summary="获取指定用户详情")
async def get_user(user_id: int):
    # 模拟：从数据库查询
    for user in FAKE_DB:
        if user["id"] == user_id:
            return user
            
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, 
        detail="User not found"
    )

@router.get("/", response_model=List[UserOut], summary="获取所有用户列表")
async def list_users():
    return FAKE_DB
