from typing import Generator
from app.db.session import SessionLocal

def get_db() -> Generator:
    """
    FastAPI 依赖注入：获取数据库 Session。
    每次请求时创建一个新的数据库 Session，请求结束时自动关闭。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
