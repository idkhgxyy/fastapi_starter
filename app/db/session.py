from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.logging import logger
from app.core.config import settings

# 从统一的配置中心读取数据库连接地址
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

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
