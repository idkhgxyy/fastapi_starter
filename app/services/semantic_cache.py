"""语义缓存：相似问题直接复用历史回答，免调用 LLM。

原理：问题向量化后到 qa_cache_entries 里做余弦相似度检索，
相似度超过阈值即视为"同一个问题"，直接返回缓存的回答。
命中可省下一次完整的 LLM 调用（成本 + 延迟），并按定价中心
折算节省金额随回复告知用户。

设计要点：
- 按用户隔离：BYOK 场景下不同用户的问答互不可见
- 向量来自与 RAG 相同的本地 embedding 服务（bge-m3），零额外成本
- 查询/写入失败一律静默降级（缓存不可用不能影响正常对话）
- 多意图/长问句不进缓存：向量相似不代表问题相同，复用会漏答
- 两段式判定：≥0.95 直接命中；0.80–0.95 由 LLM 判断是否同一问题
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.qa_cache import QACacheEntry
from app.models.user import User
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


_NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
_ENTITY_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._+-]+")


def _numeric_tokens(question: str) -> set:
    """数字/岗位编号里的数字部分：变了就不是同一个问题，不能直接复用答案。"""
    return set(_NUMBER_TOKEN_RE.findall(question))


def _entity_tokens(question: str) -> set:
    """提取英文/型号类专有名词（BERT、CoT、GSM8K…），用于高相似度时的对象校验。"""
    tokens = (token.strip("._+-").lower() for token in _ENTITY_TOKEN_RE.findall(question))
    return {token for token in tokens if token}


CACHEABLE_MAX_QUERY_CHARS = 80
MULTI_INTENT_MARKERS = (
    "还有",
    "以及",
    "同时",
    "并且",
    "另外",
    "分别",
    "各自",
    "顺便",
    "补充",
    "再问",
    "对比",
    "比较",
    "区别",
    "差异",
    "异同",
)


def is_cacheable_question(question: str) -> bool:
    """多意图/长问句不查也不写缓存，避免把不同问题当成同一个问题复用答案。"""
    text = question.strip()
    if not text or len(text) > CACHEABLE_MAX_QUERY_CHARS:
        return False
    if text.count("?") + text.count("？") >= 2 or "\n" in text:
        return False
    return not any(marker in text for marker in MULTI_INTENT_MARKERS)


def _python_scan(
    db: Session, user_id: Optional[int], vector: list, limit: int
) -> List[Tuple[QACacheEntry, float]]:
    """sqlite / 无 pgvector 环境的回退：逐条算相似度，按高到低返回前 N 条。"""
    stmt = select(QACacheEntry).where(QACacheEntry.embedding_model == settings.EMBEDDING_MODEL_NAME)
    if user_id is not None:
        stmt = stmt.where(QACacheEntry.user_id == user_id)
    scored: List[Tuple[QACacheEntry, float]] = []
    for entry in db.execute(stmt).scalars():
        try:
            similarity = _cosine_similarity(vector, _parse_embedding(entry.embedding))
        except Exception as exc:
            logger.warning(f"语义缓存条目解析失败，已跳过 (id={entry.id}): {exc}")
            continue
        scored.append((entry, similarity))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


async def _embed_query(db: Session, text: str) -> list:
    rag = RAGService(db)
    return (await rag.get_embeddings([text]))[0]


async def _judge_same_question(
    db: Session, user_id: Optional[int], cached_question: str, new_question: str
) -> bool:
    """灰区校验：让模型判断两个问题是否在问同一件事（对象/数字/范围一致）。"""
    from app.services.llm_observability_service import create_llm_call_log
    from app.services.llm_service import get_llm_client

    try:
        user = db.get(User, user_id) if user_id is not None else None
        info = get_llm_client(user)
        if not getattr(info.client, "api_key", None):
            return False

        started = time.perf_counter()
        response = await info.client.chat.completions.create(
            model=info.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是语义缓存校验器。判断两个问题是否在问同一件事，"
                        "要求对象、数字、范围和意图一致。只回答「是」或「否」，不要解释。"
                    ),
                },
                {"role": "user", "content": f"问题A：{cached_question}\n问题B：{new_question}"},
            ],
            temperature=0,
            max_tokens=3,
            extra_body={"thinking": {"type": "disabled"}},
        )
        answer = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
        create_llm_call_log(
            db,
            user_id=user_id,
            endpoint="/semantic-cache/verify",
            prompt=f"问题A：{cached_question}\n问题B：{new_question}",
            response=answer,
            tool_calls=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=(time.perf_counter() - started) * 1000,
            status="success",
            model_name=info.model_name,
            provider="semantic_cache_verify",
        )
        return answer.startswith("是") or answer.lower().startswith("yes")
    except Exception as exc:
        logger.warning(f"语义缓存候选校验失败，按不命中处理: {exc}")
        return False


async def lookup_semantic_cache(
    db: Session,
    user_id: Optional[int],
    question: str,
    *,
    require_sources: bool = False,
    query_vector: Optional[list] = None,
) -> Optional[Tuple[QACacheEntry, float]]:
    """查询语义缓存。命中返回 (条目, 相似度)，未命中/被禁用/出错返回 None。

    依次检查最近 N 条候选，而不是只取 top1：最近一条可能因为数字/来源
    守卫被拒，但后面仍有合法条目。require_sources=True 时，无来源快照的
    旧条目/聊天缓存按未命中处理，让 RAG 重新检索并写入带来源的缓存。
    """
    if not settings.SEMANTIC_CACHE_ENABLED:
        return None
    if not is_cacheable_question(question):
        return None

    if query_vector is None:
        try:
            query_vector = await _embed_query(db, question)
        except Exception as e:
            logger.warning(f"语义缓存查询失败（embedding 不可用，跳过缓存）: {e}")
            return None

    limit = max(1, int(settings.SEMANTIC_CACHE_TOP_CANDIDATES))
    candidates: List[Tuple[QACacheEntry, float]] = []
    try:
        distance_expr = QACacheEntry.embedding.cosine_distance(query_vector).label("distance")
        stmt = select(QACacheEntry, distance_expr).where(
            QACacheEntry.embedding_model == settings.EMBEDDING_MODEL_NAME
        )
        if user_id is not None:
            stmt = stmt.where(QACacheEntry.user_id == user_id)
        stmt = stmt.order_by(distance_expr).limit(limit)
        rows = db.execute(stmt).all()
        candidates = [(entry, 1.0 - float(distance)) for entry, distance in rows]
    except Exception:
        # sqlite / 未装 pgvector 扩展的环境：回退到 Python 端计算
        db.rollback()
        try:
            candidates = _python_scan(db, user_id, query_vector, limit)
        except Exception as exc:
            logger.warning(f"语义缓存回退扫描失败，跳过缓存: {exc}")
            return None

    if not candidates:
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = None
    if settings.SEMANTIC_CACHE_TTL_DAYS > 0:
        cutoff = now - timedelta(days=settings.SEMANTIC_CACHE_TTL_DAYS)

    for entry, similarity in candidates:
        if similarity < settings.SEMANTIC_CACHE_CANDIDATE_THRESHOLD:
            continue
        if cutoff is not None and entry.created_at and entry.created_at < cutoff:
            logger.info(f"==> 语义缓存候选已过期 (id={entry.id}, 相似度 {similarity:.3f})")
            continue
        if _numeric_tokens(entry.question) != _numeric_tokens(question):
            logger.info("==> 语义缓存候选数字/岗位编号不一致，检查下一条")
            continue
        if require_sources and not entry.source_chunks:
            logger.info("==> 语义缓存候选缺少来源，检查下一条")
            continue

        # 专有名词变化（BERT→Transformer 等）即便高相似度也不能直接复用
        needs_judge = similarity < settings.SEMANTIC_CACHE_THRESHOLD or (
            _entity_tokens(entry.question) != _entity_tokens(question)
        )
        if needs_judge:
            same_question = await _judge_same_question(db, user_id, entry.question, question)
            logger.info(
                f"==> 语义缓存候选校验 (相似度 {similarity:.3f}, "
                f"校验={'通过' if same_question else '拒绝'})"
            )
            if not same_question:
                continue

        try:
            entry.hit_count += 1
            entry.last_hit_at = now
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"语义缓存命中记账失败，跳过缓存: {exc}")
            return None

        logger.info(
            f"==> 语义缓存命中 (相似度 {similarity:.3f}, "
            f"节省 ¥{entry.original_cost_cny:.4f}, 第 {entry.hit_count} 次命中)"
        )
        return entry, similarity

    return None


def _prune_user_cache(db: Session, user_id: Optional[int]) -> None:
    """按 TTL 和单用户上限清理缓存；失败只告警，不影响本次写入。"""
    if user_id is None:
        return
    try:
        if settings.SEMANTIC_CACHE_TTL_DAYS > 0:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                days=settings.SEMANTIC_CACHE_TTL_DAYS
            )
            db.query(QACacheEntry).filter(
                QACacheEntry.user_id == user_id,
                QACacheEntry.created_at < cutoff,
            ).delete(synchronize_session=False)

        max_entries = int(settings.SEMANTIC_CACHE_MAX_ENTRIES_PER_USER)
        if max_entries > 0:
            stale_ids = [
                row[0]
                for row in (
                    db.query(QACacheEntry.id)
                    .filter(QACacheEntry.user_id == user_id)
                    .order_by(QACacheEntry.created_at.desc())
                    .offset(max_entries)
                    .all()
                )
            ]
            if stale_ids:
                db.query(QACacheEntry).filter(QACacheEntry.id.in_(stale_ids)).delete(
                    synchronize_session=False
                )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"语义缓存清理失败（不影响对话）: {e}")


async def store_semantic_cache(
    db: Session,
    user_id: Optional[int],
    question: str,
    answer: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    original_cost_cny: float,
    source_chunks: Optional[List[str]] = None,
    query_vector: Optional[list] = None,
) -> None:
    """把一轮成功问答写入缓存。失败静默降级，不影响对话。"""
    if not settings.SEMANTIC_CACHE_ENABLED:
        return
    if not is_cacheable_question(question):
        return
    try:
        vector = query_vector
        if vector is None:
            vector = await _embed_query(db, question)
        db.add(
            QACacheEntry(
                user_id=user_id,
                question=question,
                answer=answer,
                source_chunks=source_chunks,
                embedding=vector,
                model_name=model_name,
                embedding_model=settings.EMBEDDING_MODEL_NAME,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                original_cost_cny=original_cost_cny,
            )
        )
        db.commit()
        _prune_user_cache(db, user_id)
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
    ).where(QACacheEntry.embedding_model == settings.EMBEDDING_MODEL_NAME)
    if user_id is not None:
        stmt = stmt.where(QACacheEntry.user_id == user_id)
    rows = db.execute(stmt).all()
    return {
        "cache_entries": len(rows),
        "cache_hits": sum(r.hit_count for r in rows),
        "cache_saved_cny": round(sum(r.hit_count * r.original_cost_cny for r in rows), 4),
    }
