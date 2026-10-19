import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 测试环境标记（禁用 Rate Limiter 等）
os.environ["TESTING"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.db.base import Base
from app.main import app

DEFAULT_SQLITE_URL = "sqlite:///:memory:"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

USING_POSTGRES = DATABASE_URL.startswith("postgresql")

# ⚠️ 防呆守卫（2026-10-20 加，别再摘掉）
# 本文件在 session 结束时会执行 Base.metadata.drop_all()。曾经因为在容器里直接跑
# pytest（容器环境变量带着真实 Postgres URL）把整库清空过一次：账号、BYOK 密钥配置、
# 知识库文档全部丢失。服务器上现在跑的是有真实数据的库，这条从"警惕"升级为"红线"。
# 因此默认拒绝在 PostgreSQL 上跑测试，只有显式声明"我知道这是一次性库"才放行——
# CI 的 postgres 服务容器就是一次性库，它在 ci.yml 里显式设了该变量。
if USING_POSTGRES and os.getenv("ALLOW_DESTRUCTIVE_DB_TESTS") != "1":
    raise RuntimeError(
        "\n拒绝在 PostgreSQL 上跑测试：conftest 会在测试结束时 drop_all 清空整库。\n"
        f"  当前 DATABASE_URL = {DATABASE_URL}\n"
        "  二选一：\n"
        "    1) 用内存 sqlite（推荐，也是 make test 的行为）：\n"
        "       DATABASE_URL='sqlite:///:memory:' python -m pytest tests/\n"
        "    2) 确认这是一次性数据库（如 CI 服务容器）后显式放行：\n"
        "       ALLOW_DESTRUCTIVE_DB_TESTS=1 python -m pytest tests/\n"
    )

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
    if USING_POSTGRES:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
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
