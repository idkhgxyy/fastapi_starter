#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.document import DOCUMENT_STATUS_READY, Document, DocumentChunk
from app.models.task import Task
from app.models.user import User

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo123456"


def seed():
    logger.info("=== Seeding demo data ===")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        existing = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": DEMO_EMAIL},
        ).fetchone()

        if existing:
            logger.info(f"Demo user already exists (id={existing[0]}), skipping seed.")
            return

        demo_user = User(
            username="demo",
            email=DEMO_EMAIL,
            full_name="Demo User",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            is_active=True,
        )
        db.add(demo_user)
        db.flush()
        logger.info(f"Created demo user (id={demo_user.id}, password={DEMO_PASSWORD})")

        doc = Document(
            owner_id=demo_user.id,
            filename="welcome.txt",
            file_type="txt",
            content=(
                "欢迎使用 FastAPI Starter 知识库系统！\n\n"
                "这是一个基于 RAG（检索增强生成）的智能问答系统。\n"
                "它的工作原理如下：\n"
                "1. 上传文档后，系统会自动切分文本、生成向量并存入 pgvector\n"
                "2. 提问时，先检索最相关的文档片段\n"
                "3. 可选的 BGE-Reranker 对候选片段进行重排序\n"
                "4. 将最相关的片段作为上下文发送给大模型生成答案\n\n"
                "系统还支持 Tool Calling（天气查询、任务管理、计算器、系统状态）、\n"
                "多轮对话记忆、SSE 流式输出、API Key 加密存储等高级功能。\n"
                "试试问我：'这个系统有哪些功能？'"
            ),
            status=DOCUMENT_STATUS_READY,
            chunks_count=1,
        )
        db.add(doc)
        db.flush()
        logger.info(f"Created demo document (id={doc.id})")

        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content=doc.content,
            embedding=[0.0] * settings.EMBEDDING_DIMENSION,
        )
        db.add(chunk)

        tasks_data = [
            {
                "title": "了解 RAG 工作原理",
                "description": "阅读项目文档了解检索增强生成",
                "status": "completed",
            },
            {
                "title": "配置 LLM API Key",
                "description": "在个人设置中配置自己的大模型 API Key",
                "status": "pending",
            },
            {
                "title": "体验 Tool Calling",
                "description": "向 AI 询问天气或创建任务",
                "status": "pending",
            },
        ]
        for t in tasks_data:
            db.add(Task(owner_id=demo_user.id, **t))

        logger.info(f"Created {len(tasks_data)} demo tasks")

        db.commit()
        logger.info("=== Seed complete! ===")
        logger.info(f"Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")

    except Exception as e:
        db.rollback()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
