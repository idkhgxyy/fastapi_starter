# AGENTS.md

本文件是 AI 编码工具的唯一权威规则。`CLAUDE.md` 只是指向这里的指针。
动手前先读本文件；细节按文末「阅读策略」按需查，不要整篇读历史文档。

## 项目与命令

FastAPI + SQLAlchemy 2 + PostgreSQL/pgvector + Redis + Celery/beat + React/Vite。

- 本地启动：`docker compose up -d`
- 测试：`make test`（强制 sqlite 内存库，安全入口）
  - 等价命令：`docker compose exec -e DATABASE_URL='sqlite:///:memory:' api pytest tests/ -q`
- 格式与静态检查：`docker compose exec api ruff format app tests && docker compose exec api ruff check app tests`
- RAG/缓存评测：`docker compose exec -w /app -e PYTHONPATH=/app api python scripts/rag_eval.py`（需要真实知识库；`--skip-cache` 只跑检索）
- 部署后冒烟：`make smoke`（或服务器上 `docker exec -w /app -e PYTHONPATH=/app fastapi-starter-api python scripts/smoke_test.py`）；专用 `smoke@example.com` 账号，覆盖健康/上传/RAG/缓存/流式/清理
- 浏览器冒烟：本机 `/usr/bin/python3 scripts/ui_smoke_test.py`；服务器前端只监听 127.0.0.1，先建隧道 `ssh -N -L 18081:127.0.0.1:8000 ubuntu@YOUR_SERVER`，再设 `UI_SMOKE_BASE_URL=http://127.0.0.1:18081`
- 迁移：改 `app/models/` 后 `alembic revision --autogenerate -m "..."` → 审查 → `alembic upgrade head`；新模型要在 `app/models/__init__.py` 导入
- 前端：`cd frontend && npm run build`；不要在 2G 服务器上构建
- 依赖：运行时写 `requirements.txt`，测试/开发写 `requirements-dev.txt`；改依赖必须重建镜像

## 分层与风格

- `app/api/routers/`：HTTP、参数校验、响应；不写业务逻辑
- `app/services/`：业务逻辑；`app/models/`：ORM；`app/schemas/`：Pydantic；`app/worker/`：Celery 耗时任务
- DB 走 `Depends(get_db)`，SQLAlchemy 用 2.0 风格（`select()` / `execute().scalars()`）
- 日志用 `app.core.logging.logger`，不要 `print()`
- 异常按所在模块现有模式：API 路由多用 `HTTPException`，worker/部分接口用 `AppException`；不要为“统一”大范围重构
- 所有函数写类型提示；核心逻辑变更补 pytest

## 不能改坏的约定

- **流式**（`/chat/`、`/rag/query/stream`）：日志、落库、摘要、缓存写入全部在 `data: [DONE]` 之前完成；`[DONE]` 必须是最后一条。客户端断开时生成器会被取消，收尾放后面等于不执行。
- **语义缓存**：聊天和 RAG 都只在会话首轮读写；知识库变化（处理完成/删除/重传/摘要落库）按用户失效。两段式判定：相似度 ≥0.95 直接命中；0.80–0.95 由一次短 LLM 校验“是否同一问题”；多意图/长问句/对比类不查也不写。取最近 3 条候选逐条过守卫；数字/岗位编号不一致直接拒，英文专有名词变化即使高相似也校验。RAG 命中返回 `source_chunks`，无来源按未命中。缓存有 30 天 TTL、单用户 200 条上限，并按 `embedding_model` 隔离模型版本。
- **RAG 切块**：Markdown 按 `\n## ` / `\n# ` 标题优先切分，每个 chunk 前置文档标题；改切块逻辑必须用 DB 里的 `content` 重建受影响文档的 chunks（不要重传，摘要保留）。
- **检索加权**：查询含岗位编号/长数字（如 J106366、78567）时扩大召回，并按候选是否包含该标识做词法加权。
- **摘要兜底**：全局性问题（总结/串讲/对比/差异/哪份/哪些岗位…）注入摘要；上限 20 篇、单篇预览 320 字。改这里跑 `tests/test_rag.py` 与 `tests/test_rag_service.py`。
- **Agent 目标任务**：只在 owner 的 ready 文档内检索；执行前查预算；单节 2800 tokens；材料首行必须写「共 N 篇文档」，统计只引用材料中明确写出的条目。
- **Celery/beat**：worker 不在 `--reload`；改 `app/worker/*`、beat 或环境变量后必须重启 `celery_worker`。改 `.env` 后 `docker compose restart` 不会重载 api 的 `env_file`，需 `up -d --force-recreate api celery_worker`。
- **临时脚本**：不要放进 `/app`（watchfiles 会重启 uvicorn，掐断进行中的流式请求）；放 `/tmp`，用 `docker exec -w /app -e PYTHONPATH=/app` 执行。
- **数据库测试**：conftest 会 `drop_all`。Postgres 上默认拒绝，必须显式 `ALLOW_DESTRUCTIVE_DB_TESTS=1`；不要随手加这个变量，`make test` 已是安全入口。
- **部署顺序**：停 api → 同步代码/迁移 → `alembic upgrade head` → 启 api。服务器无 git，靠 rsync；具体命令与访问方式见本地 `HANDOFF.md`。
- **资源约束**：线上是 2G 小机器；不引入 Ollama、本地重排、本地 OCR 等吃内存组件（相关能力走云端 API）。
- **不建议的方向**：云端 rerank 已实测反而降质，`top_k` 3→5 已拍板不改；不要重复尝试。

## 阅读策略

默认只读本文件，然后直接看相关代码与测试。

- 部署/线上排障：只读 `HANDOFF.md` 的「当前状态 / 部署 runbook / 未决问题」三节，不要整篇读。
- 改检索、成本、会话：直接读对应 service 与其测试；需要模块全景时读 `docs/ARCHITECTURE.md`。
- `docs/archive/CODE_WIKI-2026-06.md` 是 2026-06 的历史快照，事实以代码和本文件为准，不主动读。
- `docs/` 下 `FRONTEND_PRD.md`、`PROJECT_REVIEW.md`、`IMPROVEMENT_PLAN.md`、`changes.md`、`project_mvp.md`、`DEPLOY_RAILWAY.md` 均为历史文档，不主动读。
- `README*.md` 面向人，不主动读；需要对外描述时再看。
- 新的跨会话约束更新本文件；会话进展写 `HANDOFF.md`；不要每次改动都同步 README / CODE_WIKI / changes。

## 验证底线

- 改后端：跑相关 pytest，必要时全量 `make test`
- 改前端：至少 `npm run build`
- 改 RAG / Agent：用真实文档走一遍检索或目标任务，对照原文核对结果
- 部署后：跑 `make smoke`（或服务器上的 smoke_test.py），失败按真实故障处理
- 没有实际输出/run 证据，不要说“已验证”；CI 是否绿以真实 run 为准
