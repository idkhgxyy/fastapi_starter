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

## 基线（2026-10-27）

- 检索：n=27，recall@3=1.00，MRR=0.963，keyword_hit=1.00，evidence_hit=1.00。
- 缓存：pairs=8，paraphrase_hit=1.00，negative_reject=1.00。

改检索、切块或缓存逻辑后重跑，对比这两行即可。新增/修改文档时同步更新 `expected_documents` 的文件名。

## 部署后冒烟

评测集验证检索/缓存内部，不覆盖 HTTP、登录、上传、Celery 和流式。部署后另跑：

```bash
make smoke
# 服务器上：
sudo docker exec -w /app -e PYTHONPATH=/app fastapi-starter-api python scripts/smoke_test.py
```

脚本使用专用 `smoke@example.com` 账号（首次自动注册，可用 `SMOKE_EMAIL`/`SMOKE_PASSWORD` 覆盖；默认账号只适合本机/内网），上传一篇唯一事实的临时文档，验证健康检查、ready、真实 RAG、缓存命中、换数字拒绝、流式 `[DONE]` 和清理；任何一步失败返回非 0。

浏览器层（需本机 Playwright）：

```bash
# 服务器前端只监听 127.0.0.1，先建隧道
ssh -N -L 18081:127.0.0.1:8000 ubuntu@YOUR_SERVER
UI_SMOKE_BASE_URL=http://127.0.0.1:18081 /usr/bin/python3 scripts/ui_smoke_test.py
```

覆盖登录页、侧栏上传到“就绪”、知识库搜索、知识库问答与来源、对话框提问、流式结束和清理；失败/成功截图写到 `evaluation/artifacts/`（gitignored）。
