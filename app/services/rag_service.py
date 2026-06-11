import asyncio
import json
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.document import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PROCESSING,
    DOCUMENT_STATUS_QUEUED,
    DOCUMENT_STATUS_READY,
    Document,
    DocumentChunk,
)

try:
    from sentence_transformers import CrossEncoder

    _reranker = None
except ImportError:
    CrossEncoder = None
    _reranker = None

_embedding_client = None


def _get_embedding_client() -> AsyncOpenAI:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = AsyncOpenAI(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        )
    return _embedding_client


def get_reranker():
    global _reranker
    if CrossEncoder is not None and _reranker is None:
        logger.info("==> 正在加载 BGE-Reranker 模型，这可能需要一点时间...")
        _reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
    return _reranker


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=50, separators=["\n\n", "\n", " ", ""]
        )

    def create_document_record(
        self, *, filename: str, content: str, owner_id: int, file_type: str = "txt"
    ) -> Document:
        document = Document(
            owner_id=owner_id,
            filename=filename,
            file_type=file_type,
            content=content,
            status=DOCUMENT_STATUS_QUEUED,
            chunks_count=0,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def attach_processing_task(self, *, document_id: int, owner_id: int, task_id: str) -> Document:
        document = self.get_document_for_user(document_id=document_id, owner_id=owner_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found for user {owner_id}")

        document.processing_task_id = task_id
        document.status = DOCUMENT_STATUS_QUEUED
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_documents_for_user(self, *, owner_id: int) -> List[Document]:
        stmt = (
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_document_for_user(self, *, document_id: int, owner_id: int) -> Optional[Document]:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.owner_id == owner_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_document_by_task_id_for_user(
        self, *, task_id: str, owner_id: int
    ) -> Optional[Document]:
        stmt = select(Document).where(
            Document.processing_task_id == task_id,
            Document.owner_id == owner_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def delete_document(self, *, document_id: int, owner_id: int) -> Optional[Document]:
        document = self.get_document_for_user(document_id=document_id, owner_id=owner_id)
        if document is None:
            return None
        self.db.delete(document)
        self.db.commit()
        return document

    def has_ready_documents(self, *, owner_id: int) -> bool:
        stmt = select(func.count(Document.id)).where(
            Document.owner_id == owner_id,
            Document.status == DOCUMENT_STATUS_READY,
        )
        return bool(self.db.scalar(stmt))

    def mark_document_processing(
        self, *, document_id: int, task_id: Optional[str] = None
    ) -> Document:
        document = self.db.get(Document, document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")

        document.status = DOCUMENT_STATUS_PROCESSING
        document.error_message = None
        if task_id:
            document.processing_task_id = task_id
        self.db.commit()
        self.db.refresh(document)
        return document

    def mark_document_failed(
        self, *, document_id: int, error_message: str, task_id: Optional[str] = None
    ) -> None:
        document = self.db.get(Document, document_id)
        if document is None:
            return

        document.status = DOCUMENT_STATUS_FAILED
        document.error_message = error_message[:2000]
        if task_id:
            document.processing_task_id = task_id
        self.db.commit()

    def requeue_document(self, *, document_id: int, owner_id: int, task_id: str) -> Document:
        document = self.get_document_for_user(document_id=document_id, owner_id=owner_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found for user {owner_id}")

        document.status = DOCUMENT_STATUS_QUEUED
        document.processing_task_id = task_id
        document.error_message = None
        document.chunks_count = 0
        self.db.commit()
        self.db.refresh(document)
        return document

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """调用 Embedding API 获取向量表示"""
        try:
            # 去除多余的空格，减少无意义 token
            texts = [text.replace("\n", " ") for text in texts]
            response = await _get_embedding_client().embeddings.create(
                input=texts, model=settings.EMBEDDING_MODEL_NAME
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            raise e

    async def process_document(
        self, *, document_id: int, task_id: Optional[str] = None
    ) -> Document:
        """处理已上传文档：切分、生成向量并写入向量表。"""
        document = self.mark_document_processing(document_id=document_id, task_id=task_id)

        chunks = self.text_splitter.split_text(document.content)
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        self.db.flush()

        if not chunks:
            document.chunks_count = 0
            document.status = DOCUMENT_STATUS_READY
            document.error_message = None
            self.db.commit()
            self.db.refresh(document)
            return document

        batch_size = 10
        embeddings: List[List[float]] = []
        for index in range(0, len(chunks), batch_size):
            batch_chunks = chunks[index : index + batch_size]
            batch_embeddings = await self.get_embeddings(batch_chunks)
            embeddings.extend(batch_embeddings)

        db_chunks = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            db_chunks.append(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk_text,
                    embedding=embedding,
                )
            )

        self.db.add_all(db_chunks)
        document.chunks_count = len(db_chunks)
        document.status = DOCUMENT_STATUS_READY
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)
        return document

    async def retrieve_relevant_chunks(
        self, *, query: str, owner_id: int, top_k: int = 3
    ) -> List[DocumentChunk]:
        """根据 query 检索最相关的 DocumentChunks，并在可用时做重排。"""
        if not self.has_ready_documents(owner_id=owner_id):
            return []

        query_embeddings = await self.get_embeddings([query])
        query_vector = query_embeddings[0]
        recall_k = top_k * 3

        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                Document.owner_id == owner_id,
                Document.status == DOCUMENT_STATUS_READY,
            )
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(recall_k)
        )

        result = self.db.execute(stmt)
        candidates = result.scalars().all()
        if not candidates:
            return []

        reranker = get_reranker()
        if reranker is None:
            logger.warning("未安装 sentence-transformers 或重排模型不可用，跳过重排步骤。")
            return candidates[:top_k]

        logger.info(f"==> 使用 BGE-Reranker 对 {len(candidates)} 个候选片段进行重排...")
        pairs = [[query, chunk.content] for chunk in candidates]
        scores = await self._predict_rerank_scores(reranker, pairs)

        scored_candidates = list(zip(candidates, scores))
        scored_candidates.sort(key=lambda item: item[1], reverse=True)

        for rank, (chunk, score) in enumerate(scored_candidates[:top_k], start=1):
            logger.info(f"重排 Rank {rank} (Score: {score:.4f}): {chunk.content[:60]}...")

        return [item[0] for item in scored_candidates[:top_k]]

    async def _predict_rerank_scores(self, reranker, pairs: list[list[str]]) -> list[float]:
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, reranker.predict, pairs)
        return list(scores)


SESSION_PREFIX = "rag_session"
SESSION_TTL = 3600


async def _get_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def load_session_history(user_id: int, session_id: str) -> list[dict]:
    key = f"{SESSION_PREFIX}:{user_id}:{session_id}"
    r = await _get_redis()
    raw = await r.get(key)
    if raw:
        return json.loads(raw)
    return []


async def save_session_history(user_id: int, session_id: str, history: list[dict]):
    key = f"{SESSION_PREFIX}:{user_id}:{session_id}"
    r = await _get_redis()
    await r.set(key, json.dumps(history, ensure_ascii=False), ex=SESSION_TTL)


async def append_session_message(user_id: int, session_id: str, role: str, content: str):
    history = await load_session_history(user_id, session_id)
    history.append({"role": role, "content": content})
    if len(history) > 20:
        history = history[-20:]
    await save_session_history(user_id, session_id, history)
