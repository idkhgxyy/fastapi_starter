# RAG 评测集

用真实知识库问题量化检索和语义缓存改动，不依赖 LLM 打分。

## 文件

- `rag_eval_set.jsonl`：27 条检索题，覆盖 4 篇 arXiv 和 15 篇雅思/课设/JD。
- `rag_cache_eval_set.jsonl`：8 组缓存对照，每组包含同义改写（应命中）和负数（应拒绝）。
- `../scripts/rag_eval.py`：runner。

## 运行

```bash
# 完整评测（检索 + 缓存）
docker compose exec -w /app -e PYTHONPATH=/app api python scripts/rag_eval.py

# 只跑检索，或只跑前 10 条
docker compose exec -w /app -e PYTHONPATH=/app api python scripts/rag_eval.py --skip-cache --limit 10
```

需要真实知识库和 embedding Key；缺失的用户/文档会打印 `SKIP`。缓存评测使用临时 SQLite，不读写线上 `qa_cache_entries`；灰区负数会触发一次短 LLM 校验。

## 指标

- `recall@k`：期望文档是否出现在 top-k 检索结果。
- `MRR`：第一个期望文档的倒数排名。
- `keyword_hit`：期望文档的 top-k 片段是否包含任一期望关键词。
- `evidence_hit`：同时满足文档命中与关键词命中。
- `cache paraphrase_hit`：同义改写命中率。
- `cache negative_reject`：换实体/数字/多意图的拒绝率。

## 基线（2026-10-26）

- 检索：n=27，recall@3=1.00，MRR=0.963，keyword_hit=1.00，evidence_hit=1.00。
- 缓存：pairs=8，paraphrase_hit=1.00，negative_reject=1.00。

改检索、切块或缓存逻辑后重跑，对比这两行即可。新增/修改文档时同步更新 `expected_documents` 的文件名。
