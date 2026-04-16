from app.schemas.user import UserCreate
from app.utils.errors import AppException
from fastapi import status
from app.core.logging import logger

# --- 模拟内存数据库（从路由层移入服务层） ---
FAKE_DB = []
CURRENT_ID = 1
# -----------------------------------------------

class UserService:
    """
    User 业务逻辑服务层
    """
    
    @classmethod
    def create_user(cls, user_in: UserCreate) -> dict:
        global CURRENT_ID
        logger.info(f"Attempting to create user with email: {user_in.email}")
        
        # 检查邮箱是否已被注册
        for user in FAKE_DB:
            if user["email"] == user_in.email:
                logger.warning(f"Registration failed: Email already registered ({user_in.email})")
                raise AppException(
                    code=1001, 
                    msg="Email already registered", 
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        new_user = user_in.model_dump()
        new_user["id"] = CURRENT_ID
        new_user["is_active"] = True
        
        FAKE_DB.append(new_user)
        CURRENT_ID += 1
        
        logger.info(f"User created successfully. ID: {new_user['id']}")
        return new_user

    @classmethod
    def get_user(cls, user_id: int) -> dict:
        logger.info(f"Fetching user with ID: {user_id}")
        for user in FAKE_DB:
            if user["id"] == user_id:
                return user
                
        logger.warning(f"User fetch failed: ID {user_id} not found")
        raise AppException(
            code=1002, 
            msg="User not found", 
            status_code=status.HTTP_404_NOT_FOUND
        )

    @classmethod
    def list_users(cls) -> list:
        logger.info("Fetching all users")
        return FAKE_DB
