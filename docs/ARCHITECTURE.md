# 架构总览（当前版本）

> 面向 AI 编码工具与人类读者的当前架构参考。规则与硬性约定见仓库根目录 `AGENTS.md`。
> 2026-06 的旧版 Code Wiki 已归档到 `docs/archive/CODE_WIKI-2026-06.md`，其中测试数、重排、会话存储等描述已过期。

## 1. 定位与技术栈

面向个人/小团队的多租户 LLM 网关 + 知识库 + 目标任务平台，重点展示 AI 应用后端的成本治理与工程化能力。

- 后端：FastAPI、SQLAlchemy 2、Alembic、PostgreSQL + pgvector、Redis、Celery/beat
- 模型：OpenAI 兼容接口，BYOK（Fernet 加密）与全局 Key 兜底；默认 DashScope `deepseek-v4.1-flash`
- 前端：React + TypeScript + Vite + Tailwind（`frontend/`）
- 当前测试：230 个；迁移 head：`f6a7b8c9d0e1`

## 2. 目录地图

| 路径 | 职责 |
|---|---|
| `app/main.py` | 应用入口、lifespan、路由注册、中间件、静态前端 |
| `app/api/routers/` | HTTP 层：`auth` / `users` / `chat` / `conversations` / `agent_tasks` / `tasks` / `worker` / `rag` / `observability` / `health` |
| `app/services/` | 业务层：LLM、RAG、Agent 任务、会话、缓存、定价、预算、工具、可观测性 |
| `app/models/` | ORM：user、document、llm_call_log、model_pricing、qa_cache、task、conversation、agent_task |
| `app/schemas/` | Pydantic 请求/响应模型 |
| `app/core/` | 配置、JWT/加密、日志 |
| `app/db/` | engine、SessionLocal、Base |
| `app/worker/` | Celery 应用与任务（文档处理、摘要、Agent 产出） |
| `app/utils/` | 文件解析（txt/md/pdf/docx/pptx）、异常 |
| `tests/` | pytest，24 个测试文件 / 230 条用例 |

## 3. 主要链路

### 3.1 聊天与工具调用

`POST /api/v1/chat/`、`/api/v1/chat/stream` → `llm_service.generate_chat_reply[_stream]`

1. 预算熔断 → 语义缓存（仅会话首轮）→ 加载知识库上下文（top-3 片段；全局问题追加摘要）
2. 调模型；若返回 `tool_calls`，由 `mcp_service` 执行工具并回填，循环直到给出最终回答
3. 流式链路把日志/落库/缓存全部放在 `data: [DONE]` 之前，`[DONE]` 是最后一条
4. 有 `conversation_id` 时写 `conversations` / `conversation_messages`；否则走 Redis 兼容路径
5. 记录 `llm_call_logs`（真实模型、token、人民币成本）

### 3.2 RAG 知识库

`POST /api/v1/rag/upload` → 解析文件（20MB 上限）→ `documents` 入队 → Celery `process_document_task`

1. 切块：500 字 / 50 重叠，Markdown 优先按 `##`/`#` 标题切分；每个 chunk 前置文档标题（无 H1 用文件名）
2. Embedding（`text-embedding-v4`，1024 维）写入 `document_chunks`，状态转 `ready`
3. 查询：`/rag/search`（纯检索）、`/rag/query`（阻断式回答）、`/rag/query/stream`（SSE）
4. 全局问题（总结/串讲/对比/差异/哪份/哪些岗位…）注入最多 20 篇摘要（单篇 320 字）
5. 每晚 beat 生成缺失摘要（单轮最多 5 篇）；知识库变化时按用户失效语义缓存

### 3.3 目标型 Agent 任务

`POST /api/v1/agent-tasks/` → Celery `run_agent_task_task` → `agent_task_service.run_task`

1. 校验任务范围（仅当前用户 ready 文档）与预算
2. 材料 = 每篇摘要（首行写「共 N 篇文档」）+ 目标相关 top-6 片段
3. 固定流水线：retrieve → outline → 逐节 write（最多 5 节，单节 2800 tokens）→ finalize
4. 产出 Markdown，步骤与 token/成本写入 `agent_task_steps`；支持重试、删除、导出 `.md`

### 3.4 会话持久化

`/api/v1/conversations` 提供列表/新建/详情/删除；`/chat/` 接受 `conversation_id`。
标题取首条用户消息前 30 字；语义缓存只在首轮读写，避免多轮答案串上下文。

### 3.5 成本治理与可观测性

- `model_pricings` + `pricing_service`：模型单价中心，启动时幂等种子化
- `cost_guard`：按用户自然月预算熔断，阻断与流式链路同标准
- `semantic_cache`：余弦相似度 ≥ 0.92 复用答案；按用户隔离；知识库变化即失效
- 降级链：云端失败 → 本地/备用模型（视配置）
- `llm_call_logs` + `/api/v1/observability/*` + Prometheus：真实模型、token、成本、延迟

## 4. 关键数据表

| 表 | 用途 |
|---|---|
| `users` | 账号、BYOK 配置、预算 |
| `documents` / `document_chunks` | 知识库文档与向量片段 |
| `llm_call_logs` | 每次模型调用的用量、成本、延迟 |
| `model_pricings` | 模型单价（成本计算依据） |
| `qa_cache_entries` | 语义缓存 |
| `conversations` / `conversation_messages` | 聊天会话与消息 |
| `agent_tasks` / `agent_task_steps` | 目标任务、步骤与成本 |
| `tasks` | 聊天工具创建的待办 |

## 5. 常见改动入口

| 想改什么 | 先看哪里 |
|---|---|
| 聊天/流式/工具调用 | `app/services/llm_service.py`、`mcp_service.py`、`app/api/routers/chat.py` |
| RAG 上传/切块/检索 | `app/services/rag_service.py`、`app/utils/file_parser.py`、`app/api/routers/rag.py` |
| 目标成果流水线 | `agent_task_service.py`、`agent_tasks.py`、`app/worker/tasks.py` |
| 会话与历史 | `conversation_service.py`、`app/models/conversation.py` |
| 成本/缓存/预算 | `cost_guard.py`、`semantic_cache.py`、`pricing_service.py` |
| 鉴权/用户 | `auth_service.py`、`user_service.py`、`app/core/security.py` |
| 异步/定时任务 | `app/worker/tasks.py`、`celery_app.py` |

## 6. 当前设计决策（不要重复推翻）

- 不接云端 rerank（实测降质）；`top_k` 维持 3
- 语义缓存阈值 0.92，不调低
- 摘要注入 20 篇 / 320 字；Agent 单节 2800 tokens
- Markdown 标题切块 + 每块前置标题；改切块必须重建受影响文档 chunks
- 线上 2G 机器：不引入 Ollama、本地重排、本地 OCR
- 服务器部署细节见本地 `HANDOFF.md`（不在公开仓库）
