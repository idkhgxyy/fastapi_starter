import asyncio
import json
from dataclasses import dataclass, field
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

# 判定"全局性问题"（问整个知识库而非某个细节）的关键词。
# 这类问题的向量检索天然不占优：query 里没有具体实体，反而可能被参考文献列表这类
# 字面密集的片段抢到 top-k。命中时额外注入文档摘要，让模型看得见知识库全貌。
GLOBAL_QUERY_MARKERS = (
    "总结",
    "串讲",
    "概括",
    "概述",
    "综述",
    "梳理",
    "盘点",
    "归纳",
    "对比",
    "比较",
    "区别",
    "异同",
    "共同点",
    "联系",
    "每篇",
    "各篇",
    "这几篇",
    "这几份",
    "所有",
    "全部",
    "分别",
    "整体",
    "有哪些",
    "哪些文档",
    "哪些资料",
    "都讲了什么",
    "讲了什么",
    "讲了啥",
    "主要内容",
)

# 摘要注入上限：单篇截断 + 总篇数截断，避免知识库变大后 prompt 无上限膨胀
SUMMARY_INJECTION_MAX_DOCS = 8
SUMMARY_INJECTION_PREVIEW_CHARS = 160


def is_global_query(query: str) -> bool:
    """粗判是否为"问整个知识库"的全局性问题（关键词启发式，宁可多注入不可漏）。"""
    return any(marker in query for marker in GLOBAL_QUERY_MARKERS)


def _chunk_filename(chunk) -> Optional[str]:
    """取片段所属文档名；对测试替身等没有 document 关系的情况安全返回 None。"""
    document = getattr(chunk, "document", None)
    return getattr(document, "filename", None)


@dataclass
class KnowledgeContext:
    """一次知识库检索的结果：原文片段 + 可选的摘要兜底。

    context 为可直接注入 system prompt 的完整参考块；没有任何可用资料时为 None。
    """

    context: Optional[str] = None
    chunks: List[DocumentChunk] = field(default_factory=list)
    summary_documents: List[Document] = field(default_factory=list)
    total_ready_documents: int = 0

    def source_labels(self) -> List[str]:
        """给前端展示的来源列表：原文片段内容 + 被用到的文档摘要标签。"""
        labels = [chunk.content for chunk in self.chunks]
        labels.extend(f"《{doc.filename}》（文档摘要）" for doc in self.summary_documents)
        return labels


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
        # 先取出 owner_id：delete + commit 之后实例属性不可再访问
        owner_id = document.owner_id
        self.db.delete(document)
        self.db.commit()
        self._invalidate_semantic_cache(owner_id)
        return document

    def _invalidate_semantic_cache(self, owner_id: Optional[int]) -> None:
        """知识库内容变化后清空该用户的语义缓存（日志由 invalidate_user_cache 统一打）。

        semantic_cache 反向依赖本模块（它要复用 RAGService 做 embedding），
        所以这里只能函数内导入，避免模块级循环引用。
        """
        from app.services.semantic_cache import invalidate_user_cache

        invalidate_user_cache(self.db, owner_id)

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
        # 重新处理期间该文档不可检索，缓存里引用它的答案先作废
        self._invalidate_semantic_cache(document.owner_id)
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
            # 文档进入可检索状态 = 知识库变了，旧的问答缓存不再可信
            self._invalidate_semantic_cache(document.owner_id)
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
        # 新文档已可检索：之前基于旧知识库生成的缓存答案必须作废
        self._invalidate_semantic_cache(document.owner_id)
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

        try:
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
        except Exception:
            # sqlite / 未装 pgvector 扩展的环境：回退 Python 端计算余弦相似度
            candidates = self._python_fallback_candidates(query_vector, owner_id, recall_k)

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

    def _python_fallback_candidates(
        self, query_vector, owner_id: int, recall_k: int
    ) -> List[DocumentChunk]:
        """sqlite / 无 pgvector 环境的检索回退：逐条计算余弦相似度取最优。"""
        from app.services.semantic_cache import _cosine_similarity, _parse_embedding

        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                Document.owner_id == owner_id,
                Document.status == DOCUMENT_STATUS_READY,
            )
        )
        scored = []
        for chunk in self.db.execute(stmt).scalars():
            similarity = _cosine_similarity(query_vector, _parse_embedding(chunk.embedding))
            scored.append((similarity, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:recall_k]]

    async def _predict_rerank_scores(self, reranker, pairs: list[list[str]]) -> list[float]:
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, reranker.predict, pairs)
        return list(scores)

    def count_ready_documents(self, *, owner_id: int) -> int:
        stmt = select(func.count(Document.id)).where(
            Document.owner_id == owner_id,
            Document.status == DOCUMENT_STATUS_READY,
        )
        return int(self.db.scalar(stmt) or 0)

    def list_document_summaries(self, *, owner_id: int, limit: int) -> List[Document]:
        """取出已生成摘要的已就绪文档，按上传时间正序（便于"串讲"按脉络展开）。"""
        stmt = (
            select(Document)
            .where(
                Document.owner_id == owner_id,
                Document.status == DOCUMENT_STATUS_READY,
                Document.summary.is_not(None),
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    async def build_knowledge_context(
        self, *, query: str, owner_id: int, top_k: int = 3
    ) -> KnowledgeContext:
        """检索原文片段，并在需要时用文档摘要兜底，产出可直接注入 prompt 的参考块。

        摘要兜底解决的是向量检索的结构性短板：像"串讲四篇论文"这种没有任何具体
        实体的全局问题，top-k 很容易被参考文献列表一类字面密集的片段占据，模型
        因此只能看到零碎引用。此时把每篇文档的摘要补上，模型才能看到知识库全貌。
        """
        chunks: List[DocumentChunk] = []
        try:
            chunks = await self.retrieve_relevant_chunks(
                query=query, owner_id=owner_id, top_k=top_k
            )
        except Exception as exc:
            # embedding 调用失败等：不应连带丢掉摘要兜底，降级为"只有摘要"
            logger.warning(f"知识库检索失败，将仅尝试文档摘要兜底: {exc}")

        # 两种情况下摘要比片段更有价值：① 问的是整个知识库；② 一个片段都没检索到
        want_summaries = is_global_query(query) or not chunks
        summary_documents: List[Document] = []
        total_ready = 0
        if want_summaries:
            total_ready = self.count_ready_documents(owner_id=owner_id)
            if total_ready:
                summary_documents = self.list_document_summaries(
                    owner_id=owner_id, limit=SUMMARY_INJECTION_MAX_DOCS
                )

        if not chunks and not summary_documents:
            return KnowledgeContext(total_ready_documents=total_ready)

        context = self._render_knowledge_context(
            chunks=chunks,
            summary_documents=summary_documents,
            total_ready=total_ready,
        )
        logger.info(
            f"==> 知识库上下文：{len(chunks)} 个原文片段 + {len(summary_documents)} 篇摘要"
            f"（全局性问题={is_global_query(query)}）"
        )
        return KnowledgeContext(
            context=context,
            chunks=chunks,
            summary_documents=summary_documents,
            total_ready_documents=total_ready,
        )

    def _render_knowledge_context(
        self,
        *,
        chunks: List[DocumentChunk],
        summary_documents: List[Document],
        total_ready: int,
    ) -> str:
        parts = ["=== 知识库参考资料 ==="]
        parts.append("以下是用户个人知识库（其上传的文档）中的参考资料。")

        if summary_documents:
            header = f"【文档摘要】知识库共 {total_ready} 篇已就绪文档"
            if len(summary_documents) < total_ready:
                header += f"，以下为其中 {len(summary_documents)} 篇"
            parts.append(
                header + "。摘要是对全文的压缩，适合把握整体脉络，但不是原文；"
                "引用具体细节时应以下方原文片段为准。"
            )
            for index, document in enumerate(summary_documents, 1):
                preview = (document.summary or "").strip().replace("\n", " ")
                if len(preview) > SUMMARY_INJECTION_PREVIEW_CHARS:
                    preview = preview[:SUMMARY_INJECTION_PREVIEW_CHARS] + "…"
                parts.append(f"{index}. 《{document.filename}》：{preview}")

        if chunks:
            parts.append("【原文片段】")
            for index, chunk in enumerate(chunks, 1):
                filename = _chunk_filename(chunk)
                label = f"[片段 {index} · 来自《{filename}》]" if filename else f"[片段 {index}]"
                parts.append(f"{label}：\n{chunk.content}")
        elif summary_documents:
            parts.append(
                "【原文片段】本次没有检索到与问题直接相关的原文片段。"
                "请仅基于上面的摘要回答，并明确告知用户这是摘要层面的概括，细节需进一步检索原文。"
            )

        parts.append("=== 结束 ===")
        return "\n\n".join(parts)


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
