import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.api.deps import get_db

DEFAULT_SQLITE_URL = "sqlite:///:memory:"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

USING_POSTGRES = DATABASE_URL.startswith("postgresql")

if USING_POSTGRES:
    engine = create_engine(DATABASE_URL)
else:
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. 覆盖 FastAPI 的依赖项 (Dependency Override)
# 当测试客户端请求需要 get_db 的接口时，给它塞入我们的测试数据库 Session
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# 3. Pytest Fixtures
@pytest.fixture(scope="session")
def setup_database():
    """
    在所有测试开始前，在内存数据库里建表；测试结束后销毁。
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def client(setup_database):
    """
    提供一个可以发起 HTTP 请求的测试客户端
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session(setup_database):
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
