"""语义缓存：相似问题直接复用历史回答，免调用 LLM。

原理：问题向量化后到 qa_cache_entries 里做余弦相似度检索，
相似度超过阈值即视为"同一个问题"，直接返回缓存的回答。
命中可省下一次完整的 LLM 调用（成本 + 延迟），并按定价中心
折算节省金额随回复告知用户。

设计要点：
- 按用户隔离：BYOK 场景下不同用户的问答互不可见
- 向量来自与 RAG 相同的本地 embedding 服务（bge-m3），零额外成本
- 查询/写入失败一律静默降级（缓存不可用不能影响正常对话）
- 命中判定阈值可配（SEMANTIC_CACHE_THRESHOLD，默认 0.92）
"""

import json
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.qa_cache import QACacheEntry
from app.services.rag_service import RAGService


def _cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _parse_embedding(value) -> list:
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def _python_scan(
    db: Session, user_id: Optional[int], vector: list
) -> Tuple[Optional[QACacheEntry], float]:
    """sqlite / 无 pgvector 环境的回退：逐条计算余弦相似度取最优。"""
    stmt = select(QACacheEntry)
    if user_id is not None:
        stmt = stmt.where(QACacheEntry.user_id == user_id)
    best_entry, best_similarity = None, -1.0
    for entry in db.execute(stmt).scalars():
        similarity = _cosine_similarity(vector, _parse_embedding(entry.embedding))
        if similarity > best_similarity:
            best_entry, best_similarity = entry, similarity
    return best_entry, best_similarity


async def _embed_query(db: Session, text: str) -> list:
    rag = RAGService(db)
    return (await rag.get_embeddings([text]))[0]


async def lookup_semantic_cache(
    db: Session, user_id: Optional[int], question: str
) -> Optional[Tuple[QACacheEntry, float]]:
    """查询语义缓存。命中返回 (条目, 相似度)，未命中/被禁用/出错返回 None。"""
    if not settings.SEMANTIC_CACHE_ENABLED:
        return None
    try:
        vector = await _embed_query(db, question)
    except Exception as e:
        logger.warning(f"语义缓存查询失败（embedding 不可用，跳过缓存）: {e}")
        return None

    try:
        distance_expr = QACacheEntry.embedding.cosine_distance(vector).label("distance")
        stmt = select(QACacheEntry, distance_expr)
        if user_id is not None:
            stmt = stmt.where(QACacheEntry.user_id == user_id)
        stmt = stmt.order_by(distance_expr).limit(1)

        row = db.execute(stmt).first()
        if row is None:
            return None

        entry, distance = row
        similarity = 1.0 - float(distance)
    except Exception:
        # sqlite / 未装 pgvector 扩展的环境：回退到 Python 端计算
        db.rollback()
        entry, similarity = _python_scan(db, user_id, vector)
        if entry is None:
            return None

    try:
        if similarity < settings.SEMANTIC_CACHE_THRESHOLD:
            return None

        entry.hit_count += 1
        entry.last_hit_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        logger.info(
            f"==> 语义缓存命中 (相似度 {similarity:.3f}, "
            f"节省 ¥{entry.original_cost_cny:.4f}, 第 {entry.hit_count} 次命中)"
        )
        return entry, similarity
    except Exception as e:
        db.rollback()
        logger.warning(f"语义缓存查询失败（跳过缓存）: {e}")
        return None


async def store_semantic_cache(
    db: Session,
    user_id: Optional[int],
    question: str,
    answer: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    original_cost_cny: float,
) -> None:
    """把一轮成功问答写入缓存。失败静默降级，不影响对话。"""
    if not settings.SEMANTIC_CACHE_ENABLED:
        return
    try:
        vector = await _embed_query(db, question)
        db.add(
            QACacheEntry(
                user_id=user_id,
                question=question,
                answer=answer,
                embedding=vector,
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                original_cost_cny=original_cost_cny,
            )
        )
        db.commit()
        logger.info(f"==> 语义缓存已写入 (预计每次命中节省 ¥{original_cost_cny:.4f})")
    except Exception as e:
        db.rollback()
        logger.warning(f"语义缓存写入失败（不影响对话）: {e}")


def invalidate_user_cache(db: Session, user_id: Optional[int]) -> int:
    """知识库内容变化时清空该用户的语义缓存，返回删除条数。

    缓存按问题语义匹配，无法反查一条答案具体引用了哪些文档；而任何一篇文档的
    新增、删除、重新处理或摘要生成，都可能让历史答案不再正确（典型场景：传了
    新论文再问同一句话，命中旧答案，新论文等于白传）。因此按用户整体失效——
    缓存随时可重建，留着过期答案的风险远大于多花一次 LLM 调用。

    失败不抛出：缓存清不掉不能阻断文档处理本身，但会留 warning 日志。
    """
    if user_id is None:
        return 0
    try:
        removed = (
            db.query(QACacheEntry)
            .filter(QACacheEntry.user_id == user_id)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"语义缓存失效失败（user_id={user_id}）: {e}")
        return 0

    if removed:
        logger.info(f"==> 知识库变更，已清空用户 {user_id} 的语义缓存 {removed} 条")
    return removed


def get_cache_stats(db: Session, user_id: Optional[int]) -> dict:
    """缓存命中统计：总命中次数与累计节省金额"""
    stmt = select(
        QACacheEntry.hit_count,
        QACacheEntry.original_cost_cny,
    )
    if user_id is not None:
        stmt = stmt.where(QACacheEntry.user_id == user_id)
    rows = db.execute(stmt).all()
    return {
        "cache_entries": len(rows),
        "cache_hits": sum(r.hit_count for r in rows),
        "cache_saved_cny": round(sum(r.hit_count * r.original_cost_cny for r in rows), 4),
    }
