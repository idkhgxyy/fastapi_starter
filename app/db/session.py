import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from app.core.logging import logger

# 加载 .env 环境变量
load_dotenv()

# 获取数据库连接地址，如果环境变量没有则使用默认值
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/fastapi_db"
)

# 初始化 SQLAlchemy 同步引擎
try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,  # 每次从连接池获取连接时，验证连接是否可用
        echo=False           # 如果设为 True，会在控制台打印所有执行的 SQL 语句
    )
    
    # 初始化 Session 工厂
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure database engine: {e}")
    raise e
