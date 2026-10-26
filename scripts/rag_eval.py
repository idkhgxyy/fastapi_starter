"""RAG 检索与语义缓存评测。

在 api 容器内运行（需要真实知识库和 embedding Key）：

    python scripts/rag_eval.py
    python scripts/rag_eval.py --top-k 3 --skip-cache --limit 10

检索指标：recall@k、MRR、关键词命中、证据命中（期望文档 + 关键词）。
缓存评测在临时 SQLite 中进行，不读写线上 qa_cache_entries；同义改写应命中，
换实体/数字/多意图应拒绝。
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.llm_call_log import LLMCallLog
from app.models.model_pricing import ModelPricing  # noqa: F401  # 临时库建表用
from app.models.qa_cache import QACacheEntry
from app.models.user import User
from app.services.rag_service import RAGService
from app.services.semantic_cache import lookup_semantic_cache, store_semantic_cache

EVAL_USER_ID = 999999


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _resolve_user(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def _resolve_expected_ids(
    db: Session, user_id: int, filenames: Sequence[str]
) -> Tuple[Set[int], Set[str]]:
    docs = (
        db.query(Document)
        .filter(Document.owner_id == user_id, Document.filename.in_(filenames))
        .all()
    )
    found = {doc.filename for doc in docs}
    return {doc.id for doc in docs}, set(filenames) - found


async def _evaluate_retrieval(
    db: Session, items: List[Dict[str, Any]], top_k: int
) -> Dict[str, float]:
    service = RAGService(db)
    total = doc_hits = keyword_hits = evidence_hits = 0
    reciprocal_rank = 0.0
    skipped = 0

    for item in items:
        user = _resolve_user(db, item["user"])
        if user is None:
            print(f"[SKIP] {item['id']}: user not found: {item['user']}")
            skipped += 1
            continue

        expected_ids, missing = _resolve_expected_ids(
            db, user.id, item["expected_documents"]
        )
        if missing:
            print(f"[SKIP] {item['id']}: documents not found: {sorted(missing)}")
            skipped += 1
            continue

        chunks = await service.retrieve_relevant_chunks(
            query=item["question"], owner_id=user.id, top_k=top_k
        )
        retrieved_ids = [chunk.document_id for chunk in chunks]
        first_rank = next(
            (index + 1 for index, doc_id in enumerate(retrieved_ids) if doc_id in expected_ids),
            None,
        )
        doc_hit = first_rank is not None
        keywords = [keyword.lower() for keyword in item.get("expected_keywords", [])]
        keyword_hit = not keywords or any(
            keyword in chunk.content.lower()
            for chunk in chunks
            if chunk.document_id in expected_ids
            for keyword in keywords
        )
        evidence_hit = doc_hit and keyword_hit

        total += 1
        doc_hits += int(doc_hit)
        keyword_hits += int(keyword_hit)
        evidence_hits += int(evidence_hit)
        reciprocal_rank += (1.0 / first_rank) if first_rank else 0.0

        flag = "HIT " if evidence_hit else "MISS"
        print(
            f"[{flag}] {item['id']} rank={first_rank or '-'} "
            f"doc={int(doc_hit)} keyword={int(keyword_hit)} retrieved={retrieved_ids}"
        )

    if total == 0:
        print("retrieval: no runnable questions")
        return {"questions": 0, "skipped": skipped, "recall_at_k": 0.0, "mrr": 0.0}

    summary = {
        "questions": total,
        "skipped": skipped,
        "recall_at_k": round(doc_hits / total, 4),
        "mrr": round(reciprocal_rank / total, 4),
        "keyword_hit_rate": round(keyword_hits / total, 4),
        "evidence_hit_rate": round(evidence_hits / total, 4),
    }
    print(
        f"retrieval: n={total} recall@{top_k}={summary['recall_at_k']:.2f} "
        f"mrr={summary['mrr']:.2f} keyword_hit={summary['keyword_hit_rate']:.2f} "
        f"evidence_hit={summary['evidence_hit_rate']:.2f}"
    )
    return summary


def _make_temp_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(
        User(
            id=EVAL_USER_ID,
            username="rag-eval",
            email="rag-eval@local",
            hashed_password="not-used",
        )
    )
    db.commit()
    return db


async def _evaluate_cache(items: List[Dict[str, Any]]) -> Dict[str, float]:
    db = _make_temp_session()
    total = paraphrase_hits = negative_rejects = 0
    try:
        for item in items:
            db.query(QACacheEntry).delete()
            db.query(LLMCallLog).delete()
            db.commit()
            db.expunge_all()

            await store_semantic_cache(
                db,
                EVAL_USER_ID,
                item["base"],
                "eval-answer",
                "eval-model",
                1,
                1,
                0.0,
                source_chunks=["eval-source"],
            )
            if db.query(QACacheEntry).count() == 0:
                print(f"[WARN] {item['id']}: base question was not cached")
            paraphrase_hit = await lookup_semantic_cache(db, EVAL_USER_ID, item["paraphrase"])
            negative_hit = await lookup_semantic_cache(db, EVAL_USER_ID, item["negative"])

            paraphrase_ok = paraphrase_hit is not None
            negative_ok = negative_hit is None
            total += 1
            paraphrase_hits += int(paraphrase_ok)
            negative_rejects += int(negative_ok)

            flag = "OK  " if paraphrase_ok and negative_ok else "FAIL"
            print(
                f"[{flag}] {item['id']} paraphrase_hit={int(paraphrase_ok)} "
                f"negative_reject={int(negative_ok)}"
            )
    finally:
        db.close()

    if total == 0:
        print("cache: no runnable pairs")
        return {"pairs": 0, "paraphrase_hit_rate": 0.0, "negative_reject_rate": 0.0}

    summary = {
        "pairs": total,
        "paraphrase_hit_rate": round(paraphrase_hits / total, 4),
        "negative_reject_rate": round(negative_rejects / total, 4),
    }
    print(
        f"cache: pairs={total} paraphrase_hit={summary['paraphrase_hit_rate']:.2f} "
        f"negative_reject={summary['negative_reject_rate']:.2f}"
    )
    return summary


async def _run(args: argparse.Namespace) -> None:
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"dataset not found: {dataset_path}")

    items = _load_jsonl(dataset_path)
    if args.limit:
        items = items[: args.limit]

    db = SessionLocal()
    try:
        retrieval = await _evaluate_retrieval(db, items, args.top_k)
    finally:
        db.close()

    cache = None
    cache_path = Path(args.cache_dataset)
    if args.skip_cache:
        print("cache: skipped")
    elif not cache_path.exists():
        print(f"cache: dataset not found, skipped: {cache_path}")
    else:
        cache = await _evaluate_cache(_load_jsonl(cache_path))

    print("\nSUMMARY " + json.dumps({"retrieval": retrieval, "cache": cache}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG retrieval and semantic-cache evaluation")
    parser.add_argument("--dataset", default="evaluation/rag_eval_set.jsonl")
    parser.add_argument("--cache-dataset", default="evaluation/rag_cache_eval_set.jsonl")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-cache", action="store_true")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
