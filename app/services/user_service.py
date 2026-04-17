from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import status

from app.schemas.user import UserCreate
from app.models.user import User
from app.utils.errors import AppException
from app.core.logging import logger
from app.core.security import get_password_hash

class UserService:
    """
    User 业务逻辑服务层 (真实数据库版)
    """
    
    @classmethod
    def create_user(cls, db: Session, user_in: UserCreate) -> User:
        logger.info(f"Attempting to create user with email: {user_in.email}")
        
        # 1. 检查邮箱是否已被注册
        # select(User) 是 SQLAlchemy 2.0 的新式查询语法
        existing_user = db.execute(
            select(User).where(User.email == user_in.email)
        ).scalar_one_or_none()
        
        if existing_user:
            logger.warning(f"Registration failed: Email already registered ({user_in.email})")
            raise AppException(
                code=1001, 
                msg="Email already registered", 
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        # 2. 将 Pydantic 请求模型转换为 SQLAlchemy 数据模型，并对密码进行哈希加密
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=get_password_hash(user_in.password),
            is_active=True
        )
        
        # 3. 写入数据库并提交事务
        db.add(db_user)
        db.commit()
        db.refresh(db_user)  # 刷新以获取数据库自动生成的 id
        
        logger.info(f"User created successfully. ID: {db_user.id}")
        return db_user

    @classmethod
    def get_user(cls, db: Session, user_id: int) -> User:
        logger.info(f"Fetching user with ID: {user_id}")
        
        # db.get 是一种快捷的通过主键查询的方式
        user = db.get(User, user_id)
        if not user:
            logger.warning(f"User fetch failed: ID {user_id} not found")
            raise AppException(
                code=1002, 
                msg="User not found", 
                status_code=status.HTTP_404_NOT_FOUND
            )
        return user

    @classmethod
    def list_users(cls, db: Session) -> list[User]:
        logger.info("Fetching all users")
        # 执行查询并获取所有结果
        return list(db.scalars(select(User)).all())

    @classmethod
    def delete_user(cls, db: Session, user_id: int) -> User:
        logger.info(f"Attempting to delete user with ID: {user_id}")
        user = db.get(User, user_id)
        if not user:
            logger.warning(f"User delete failed: ID {user_id} not found")
            raise AppException(
                code=1002, 
                msg="User not found", 
                status_code=status.HTTP_404_NOT_FOUND
            )
        db.delete(user)
        db.commit()
        logger.info(f"User deleted successfully. ID: {user_id}")
        return user
