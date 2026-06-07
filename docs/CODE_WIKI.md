# FastAPI Starter - Code Wiki

## 1. 项目概述 (Project Overview)

本项目是一个基于 **FastAPI + PostgreSQL(pgvector) + Redis + Celery + Ollama** 的**个人知识库与任务执行 Agent 后端系统**。项目定位为面向实习/校招场景的后端工程项目，核心目标是展示完整的 AI 后端工程能力，而非简单的"调 API 聊天 Demo"。

### 核心特性

- **LLM Agent 与工具调用**：支持阻塞和流式对话（SSE），基于兼容 OpenAI 接口的大模型（推荐 Qwen2.5），通过 MCP 协议统一管理 5 个工具（天气查询、创建任务、系统状态查询、任务列表查询、数学计算），支持 Tool Calling 多轮调用。LLM API 调用自带指数退避重试机制（tenacity）。提供 MockLLMClient 离线演示模式。
- **RAG 知识库检索**：集成 `pgvector` 向量数据库与 LangChain 文本切分器，实现文档上传、分块、Embedding 向量化以及基于 BGE-Reranker 的高精度交叉重排。
- **多格式文档上传**：支持 `.txt` / `.md` / `.pdf` 格式的文档解析、异步切分与向量化。
- **多轮对话记忆**：基于 Redis 的 RAG 会话历史管理，支持上下文持续的问答体验。
- **异步任务与队列**：基于 Celery + Redis 实现文档解析、向量化等耗时任务的后台异步处理。
- **多租户 LLM 配置 (BYOK)**：每个用户可以独立配置自己的大模型服务商、Base URL、API Key，API Key 通过 Fernet 对称加密入库。
- **鉴权与权限**：基于 JWT 的认证体系，使用 bcrypt 进行密码哈希，支持用户级数据隔离和超级管理员权限。
- **可观测性体系**：集成 Prometheus 收集 API 指标，通过 Grafana 提供可视化看板；在数据库中记录 LLM 调用的详细日志（Token 消耗、延迟、成本、成功率等）。
- **工程化保障**：Alembic 数据库迁移、pre-commit hooks（ruff 格式化和 lint）、GitHub Actions CI（PostgreSQL 集成测试 + Docker 构建）、121 个单元测试。
- **前端应用**：React + TypeScript SPA，SSE 流式聊天、可观测性面板、Mock 离线模式。详见 [frontend/README.md](../frontend/README.md)。
- **限流保护**：基于 Redis ZSET 的滑动窗口限流，Redis 不可用时自动降级。

### 项目定位（MVP）

该项目当前的 MVP 目标是清晰证明以下 4 件事：
1. 能独立完成一个标准 Python 后端项目
2. 能把 LLM 能力接入真实后端业务链路
3. 能实现 RAG、Tool Calling、异步任务等 AI 应用核心能力
4. 有基本工程化意识，包括部署、监控、日志与可观测

详细的 MVP 说明请参考 [project_mvp.md](project_mvp.md)。

---

## 2. 项目整体架构 (Overall Architecture)

本项目遵循典型的**分层架构（Layered Architecture）**，并通过 Docker Compose 进行容器化编排。

### 技术栈

| 层级 | 技术选型 |
|------|----------|
| Web 框架 | FastAPI + Pydantic v2 (参数校验与序列化) |
| 数据库 | PostgreSQL (带 pgvector 扩展) + SQLAlchemy 2.0 ORM |
| 数据库迁移 | Alembic |
| 缓存与消息中间件 | Redis |
| 异步调度 | Celery + Flower (监控面板) |
| 大模型基座 | 兼容 OpenAI API 的客户端 (可用 Ollama 本地部署或接入云端 API) |
| 向量模型 | bge-m3 (Embedding)、BAAI/bge-reranker-base (重排) |
| 监控看板 | Prometheus + Grafana |
| 容器化 | Docker + Docker Compose |

### 请求生命周期

```
[Client HTTP Request]
        │
        ▼
[RequestIDMiddleware] ──── 注入 X-Request-ID → 响应头
        │
        ▼
[CORSMiddleware] ──── 跨域校验
        │
        ▼
[Prometheus Instrumentator] ──── 采集请求量/延迟/错误率
        │
        ▼
[FastAPI Router] ──── 路由分发 + 参数校验 (Pydantic)
        │
        ├── [Depends: get_db] ──── 获取数据库 Session
        ├── [Depends: get_current_user] ──── JWT 鉴权
        └── [Depends: RateLimiter] ──── 滑动窗口限流 (可选)
        │
        ▼
[Service Layer] ──── 核心业务逻辑
        │
        ▼
[SQLAlchemy ORM / External API] ──── 数据持久化 / LLM 调用
```

### 容器运行拓扑

```text
          [ 用户/前端 Client ]
                 │ (HTTP / SSE)
                 ▼
       [ FastAPI Application ] ──────► [ Prometheus ] ──────► [ Grafana ]
         │      │      │
(Sync/DB)│      │      │ (Async Jobs)
         ▼      │      ▼
   [PostgreSQL] │  [ Celery Worker ]
   (+ pgvector) │      │
                │      ▼
                │  [ Redis ] ◄──── [ Flower (监控面板) ]
                ▼
          [ Ollama / 云端 LLM API ]
```

---

## 3. 目录结构说明 (Directory Structure)

```text
fastapi_starter/
├── app/
│   ├── api/                # 控制器层 (Controllers/Routers)
│   │   ├── routers/        # 按业务划分的路由 (8 个模块)
│   │   │   ├── auth.py         # 用户登录 (OAuth2 Password Flow)
│   │   │   ├── chat.py         # AI 对话 (阻塞 + SSE 流式)
│   │   │   ├── health.py       # 健康检查 (DB/Redis/Ollama 依赖探针)
│   │   │   ├── observability.py# LLM 可观测 (统计 + 日志列表)
│   │   │   ├── rag.py          # RAG 知识库 (上传/查询/流式/文档管理)
│   │   │   ├── tasks.py        # 任务 CRUD
│   │   │   ├── users.py        # 用户管理 (注册/密码/Llm配置)
│   │   │   └── worker.py       # 异步任务管理 (提交/状态查询)
│   │   ├── deps.py         # FastAPI 依赖注入 (get_db, get_current_user 等)
│   │   └── middleware.py   # 自定义中间件 (RequestID 注入)
│   ├── core/               # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py       # Pydantic BaseSettings 环境变量加载
│   │   ├── security.py     # JWT 签发与密码哈希校验
│   │   └── logging.py      # 日志配置 (支持 text/json 格式, RequestID 注入)
│   ├── db/                 # 数据库连接与基类
│   │   ├── base.py         # SQLAlchemy DeclarativeBase
│   │   └── session.py      # engine 与 SessionLocal 初始化
│   ├── models/             # 领域数据模型 (SQLAlchemy 2.0 ORM)
│   │   ├── __init__.py     # 暴露所有模型供 Alembic 发现
│   │   ├── user.py         # 用户模型 (含 LLM 配置字段)
│   │   ├── task.py         # 待办任务模型
│   │   ├── document.py     # 文档与文档块模型 (含 pgvector)
│   │   └── llm_call_log.py # LLM 调用日志模型
│   ├── schemas/            # 数据传输对象 (Pydantic v2 DTOs)
│   │   ├── auth.py         # Token / TokenPayload
│   │   ├── chat.py         # ChatRequest / ChatResponse
│   │   ├── observability.py# LLMCallLogOut / DailyLLMStats / LLMStatsResponse
│   │   ├── rag.py          # DocumentResponse / RAGQueryRequest/Response
│   │   ├── task.py         # TaskCreate / TaskUpdate / TaskOut
│   │   └── user.py         # UserCreate / UserOut / UserLLMConfigUpdate / PasswordUpdate
│   ├── services/           # 业务逻辑层 (Services)
│   │   ├── auth_service.py          # 用户认证
│   │   ├── llm_service.py           # LLM Agent (对话 + Tool Calling)
│   │   ├── llm_observability_service.py # LLM 调用日志与统计
│   │   ├── mcp_service.py           # MCP 协议工具层（注册/发现/调度）
│   │   ├── rag_service.py           # RAG 知识库 (文档处理/检索/会话管理)
│   │   ├── task_service.py          # 任务管理 CRUD
│   │   └── user_service.py          # 用户管理 CRUD + LLM 配置
│   ├── utils/              # 工具类
│   │   ├── encryption.py   # Fernet 对称加解密 (API Key 加密)
│   │   ├── errors.py       # 全局业务异常 (AppException)
│   │   ├── file_parser.py  # 多格式文件解析 (txt/md/pdf)
│   │   └── rate_limit.py   # Redis ZSET 滑动窗口限流
│   ├── worker/             # Celery 任务
│   │   ├── celery_app.py   # Celery 应用配置
│   │   └── tasks.py        # 异步任务定义 (process_document_task)
│   ├── static/
│   │   └── demo.html       # 前端 Demo 页面 (TailwindCSS)
│   └── main.py             # FastAPI 实例入口与生命周期管理
├── alembic/                # 数据库迁移脚本目录
│   ├── versions/           # 8 个迁移版本
│   ├── env.py              # Alembic 环境配置
│   └── script.py.mako      # 迁移脚本模板
├── docs/                   # 项目文档
│   ├── images/             # 截图资源
│   ├── CODE_WIKI.md        # 本文档
│   ├── changes.md          # 变更记录
│   ├── FRONTEND_PRD.md     # 前端 PRD（开发前规格）
│   ├── PROJECT_REVIEW.md   # 项目评审报告
│   ├── project_mvp.md      # MVP 说明
│   └── resume_project.md   # 简历文案
├── frontend/               # React SPA 前端应用
│   ├── src/
│   │   ├── components/     # UI 组件（auth/chat/knowledge/layout/observability/tasks/ui）
│   │   ├── contexts/       # AuthContext + ThemeContext
│   │   ├── hooks/          # useChat（SSE 流式 Hook）
│   │   ├── mock/           # Mock 数据层（全 API 覆盖）
│   │   ├── pages/          # 8 个路由页面
│   │   ├── services/       # 7 个 API Service 模块
│   │   └── types/          # TypeScript 类型定义
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts      # Vite 配置（含 API 代理 + Mock 模式）
│   └── tsconfig.json       # TypeScript strict 模式
├── grafana/                # Grafana Provisioning
│   ├── dashboards/         # FastAPI 监控面板 JSON
│   └── provisioning/       # 数据源与面板自动配置
├── scripts/                # 运维与测试脚本
│   ├── bootstrap_local.sh  # 一键启动脚本
│   ├── backup_db.sh        # 数据库备份
│   ├── restore_db.sh       # 数据库恢复
│   ├── seed_demo_data.py   # Demo 种子数据
│   ├── e2e_test.py         # 端到端测试
│   ├── locustfile.py       # 压力测试脚本
│   ├── eval_llm_observability.py  # LLM 离线评测
│   ├── capture_screenshots.py     # 截图采集
│   ├── test_demo_interaction.py   # Demo 交互测试
│   └── test_rag_multiformat.py    # RAG 多格式验证
├── tests/                  # Pytest 单元测试 (121 个)
│   ├── conftest.py         # 测试配置 (支持 SQLite/PostgreSQL 双模式)
│   ├── test_auth.py
│   ├── test_auth_service.py
│   ├── test_chat_advanced.py
│   ├── test_encryption.py
│   ├── test_errors.py
│   ├── test_file_parser.py
│   ├── test_health.py
│   ├── test_llm_tools.py
│   ├── test_observability.py
│   ├── test_rag.py
│   ├── test_rag_service.py
│   ├── test_security.py
│   ├── test_task_endpoints.py
│   ├── test_user_llm_config.py
│   ├── test_user_service_direct.py
│   └── test_users.py
├── docker-compose.yml      # 容器编排 (8 个服务)
├── Dockerfile              # API/Worker 镜像
├── prometheus.yml          # Prometheus 抓取配置
├── pyproject.toml          # 项目元数据 + ruff/lint/pytest 配置
├── requirements.txt        # 生产依赖 (20 个)
├── requirements-dev.txt    # 开发/测试依赖
├── .env.example            # 环境变量模板
├── .pre-commit-config.yaml # pre-commit hooks 配置
└── CLAUDE.md               # AI 辅助编码约束文件
```

---

## 4. 主要模块职责 (Main Modules Responsibilities)

### 4.1 API 路由层 (`app/api/routers/`)

| 路由模块 | 前缀 | 职责 |
|----------|------|------|
| `health.py` | `/api/v1` | 健康检查端点，检测 Database、Redis、Ollama 依赖状态 |
| `auth.py` | `/api/v1/auth` | 用户登录（OAuth2 Password Flow），返回 JWT Token |
| `users.py` | `/api/v1/users` | 用户注册、信息查询、LLM 配置更新、密码修改、用户管理 |
| `chat.py` | `/api/v1/chat` | AI 对话（支持阻塞返回和 SSE 流式输出），挂载限流器 |
| `tasks.py` | `/api/v1/tasks` | 待办任务 CRUD（基于 owner_id 隔离） |
| `rag.py` | `/api/v1/rag` | 文档上传/列表/状态查询、知识库问答（阻塞+流式） |
| `worker.py` | `/api/v1/worker` | 异步任务提交与状态查询 |
| `observability.py` | `/api/v1/observability` | LLM 调用统计与日志列表 |

### 4.2 依赖注入层 (`app/api/deps.py`)

提供 4 层递进的依赖注入函数：

| 函数 | 用途 |
|------|------|
| `get_db()` | 获取数据库 Session，请求结束时自动关闭 |
| `get_current_user()` | 从 JWT Token 解析并验证当前用户 |
| `get_current_active_user()` | 确保用户处于激活状态 |
| `get_current_active_superuser()` | 确保用户是超级管理员（403 权限保护） |

### 4.3 核心配置模块 (`app/core/`)

| 文件 | 关键元素 | 说明 |
|------|----------|------|
| `config.py` | `Settings` 类 | 继承 `pydantic-settings.BaseSettings`，自动从 `.env` 和环境变量加载所有配置 |
| `security.py` | `verify_password()`, `get_password_hash()`, `create_access_token()` | bcrypt 密码哈希 + PyJWT Token 签发 |
| `logging.py` | `logger` 实例, `JSONFormatter`, `RequestIDFilter` | 支持 text/json 双格式日志，自动注入 RequestID |

### 4.4 LLM & Agent 模块 (`app/services/llm_service.py`)

- **核心职责**：处理与大模型的交互对话，工具调用委托给 MCPService 统一调度。
- **多轮调用链路**：
  1. **Round 1**：携带系统 Prompt + MCPService 提供的 5 个工具定义请求 LLM
  2. **Tool Execution**：解析 `response_message.tool_calls`，通过 MCPService.call_tool() 统一路由执行
  3. **Round 2**：组装工具执行结果，再次请求大模型生成自然语言回复
  4. **日志记录**：在流转末尾调用 `create_llm_call_log` 记录请求、响应与 Token 消耗
- **多租户客户端管理**：通过 `get_llm_client(user)` 函数，优先使用用户自定义的 LLM 配置（BYOK），未配置时回退到系统全局配置；开启 `LLM_MOCK=true` 时使用 MockLLMClient
- **SSE 流式支持**：`generate_chat_reply_stream()` 异步生成器，支持 `reasoning_content`（思考链）和 `content` 双字段推送
- **容错机制**：`_llm_completion_with_retry()` 使用 tenacity 实现指数退避重试，应对 429 限流和临时网络问题

**定义的 5 个工具：**

| 工具名称 | 用途 | 实现函数 |
|----------|------|----------|
| `get_current_weather` | 查询城市天气（模拟数据） | `get_current_weather(location)` |
| `create_task` | 创建待办任务（写入数据库） | `TaskService.create_task()` |
| `get_system_status` | 查询服务器 CPU/内存/磁盘状态 | `get_system_status()` (psutil) |
| `list_tasks` | 查询当前用户任务列表 | `list_tasks(db, user_id, status)` |
| `calculate` | 安全数学表达式计算 | `calculate(expression)` (AST 安全 eval) |

### 4.5 MCP 协议工具层 (`app/services/mcp_service.py`)

- **核心职责**：将系统内部工具封装为标准 MCP（Model Context Protocol）Tool 接口，提供统一的注册、发现与调用机制。
- **工具注册**：`_MCP_TOOL_DEFINITIONS` 集中定义 5 个工具的 OpenAI function calling 兼容 Schema；`_MCP_TOOL_HANDLERS` 通过 `@_register_handler` 装饰器注册处理器，声明是否需要 `db` 和 `user_id` 依赖。
- **调用入口**：
  - `MCPService.list_tools()` → 返回所有工具的 Schema 列表，供 LLM 使用
  - `MCPService.call_tool(name, arguments, db, user_id)` → 统一调度入口，自动注入依赖
- **设计价值**：工具与 LLM 服务解耦，新增工具只需在 mcp_service.py 中注册 Schema + Handler，无需修改 llm_service.py。

### 4.6 RAG 知识库模块 (`app/services/rag_service.py`)

- **核心职责**：实现文档的检索增强生成能力
- **完整处理链路**：
  1. 用户上传文件 → 解析为纯文本 → 创建 `Document` 记录（状态: `queued`）
  2. Celery Worker 异步执行 `process_document()` → 状态变为 `processing`
  3. `RecursiveCharacterTextSplitter` 按 500 字符分块（50 字符重叠）
  4. 批量调用 Embedding API（bge-m3） → 生成 1024 维向量
  5. 写入 `DocumentChunk` 表（pgvector 存储）
  6. 状态变更为 `ready`
- **检索优化**：
  1. 按用户隔离 + 仅就绪文档过滤
  2. 余弦距离初筛（召回 Top K\*3）
  3. 可选 BGE-Reranker 交叉编码器精排（返回 Top K）
- **多轮会话**：通过 `load_session_history()` / `save_session_history()` 基于 Redis 管理上下文（最多 20 轮，1 小时 TTL）

### 4.7 异步任务模块 (`app/worker/`)

| 组件 | 说明 |
|------|------|
| `celery_app.py` | Celery 应用实例，Redis 作为 Broker 和 Backend |
| `tasks.py` | `process_document_task()` — 文档切分、Embedding 和入库（支持状态回传 PROGRESS） |
| Flower | Celery 监控面板（端口 5555） |

### 4.8 鉴权与安全模块

| 层次 | 组件 | 说明 |
|------|------|------|
| 密码 | `passlib[bcrypt]` | bcrypt 哈希，自动处理 72 字节限制 |
| Token | `PyJWT` + `HS256` | JWT 签发与验证，1 小时过期（可配置） |
| API Key | `cryptography.Fernet` | 用户 LLM API Key 对称加密后入库 |
| 限流 | `rate_limit.py` | Redis ZSET 滑动窗口，60 秒/20 次（可配置） |
| 数据隔离 | owner_id 过滤 | 任务、文档均按 `owner_id` 隔离 |

### 4.9 可观测性模块

| 维度 | 实现 | 说明 |
|------|------|------|
| API 指标 | `prometheus-fastapi-instrumentator` | 自动采集 QPS、延迟、HTTP 状态码 |
| 监控看板 | Grafana | 预置 FastAPI 监控面板（`grafana/dashboards/fastapi.json`） |
| 链路追踪 | RequestIDMiddleware | 每个请求生成 UUID，注入响应头 X-Request-ID |
| LLM 日志 | `LLMCallLog` 模型 + `llm_observability_service.py` | 记录 prompt、response、tool_calls、tokens、延迟、成本、状态、错误 |
| 统计维度 | `get_llm_overview_stats()` | 按天/按端点/按用户统计调用次数、Token、成本、平均延迟 |
| 健康检查 | `/api/v1/health` | 返回 DB/Redis/Ollama 依赖状态，核心依赖异常时返回 503 |

### 4.10 中间件模块 (`app/api/middleware.py`)

| 中间件 | 职责 |
|--------|------|
| `RequestIDMiddleware` | 每个请求生成 UUID，注入 `request.state.request_id` 和 `contextvars`，响应头带 `X-Request-ID` |
| `CORSMiddleware` | 允许配置的跨域来源（默认 localhost:3000/5173/8000） |
| `Instrumentator` | Prometheus 指标采集，`/metrics` 端点暴露 |

---

## 5. 关键类与函数说明 (Key Classes & Functions)

### 5.1 配置层

#### `app.core.config.Settings`

Pydantic v2 配置类，自动从 `.env` 和环境变量加载。主要配置项分组：

| 分组 | 关键字段 | 默认值 |
|------|----------|--------|
| 项目信息 | `PROJECT_NAME`, `VERSION` | "FastAPI Starter", "0.1.0" |
| 数据库 | `DATABASE_URL`, `REDIS_URL` | postgresql://... localhost |
| JWT | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | HS256, 60 min |
| LLM | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` | DeepSeek 占位 |
| 向量 | `EMBEDDING_DIMENSION`, `EMBEDDING_MODEL_NAME` | 1024, "bge-m3" |
| 价格 | `LLM_INPUT/OUTPUT_PRICE_PER_1K_TOKENS` | 0 (成本估算用) |
| CORS | `CORS_ORIGINS` | localhost 多端口 |
| 日志 | `LOG_FORMAT` | "text" (可选 "json") |

### 5.2 数据模型层

#### `User` (`app/models/user.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int (PK) | 主键 |
| username | str(50) | 用户名，唯一索引 |
| email | str(100) | 邮箱，唯一索引 |
| full_name | str(100) nullable | 全名 |
| hashed_password | str(255) | bcrypt 哈希后的密码 |
| is_active | bool | 是否激活，默认 True |
| is_superuser | bool | 是否超级管理员，默认 False |
| llm_provider | str(50) nullable | 用户自定义 LLM 服务商 |
| llm_base_url | str(255) nullable | 用户自定义 Base URL |
| llm_model_name | str(100) nullable | 用户自定义模型名 |
| llm_api_key_encrypted | str(500) nullable | 加密后的 API Key |
| `has_custom_llm_key` | property | 是否已配置自定义 Key |

#### `Task` (`app/models/task.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int (PK) | 主键 |
| title | str(255) | 任务标题，索引 |
| description | str nullable | 任务描述 |
| status | str(50) | pending / in_progress / completed |
| owner_id | int (FK→users) | 任务所有者 |
| created_at | datetime | 创建时间 |
| `owner` | relationship | 关联 User 对象 |

#### `Document` (`app/models/document.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int (PK) | 主键 |
| owner_id | int (FK→users) nullable | 文档所有者 |
| filename | str(255) | 文件名 |
| file_type | str(16) | txt / md / pdf，默认 "txt" |
| content | text | 文档纯文本内容 |
| status | str(32) | queued / processing / ready / failed |
| chunks_count | int | 切分后的块数 |
| processing_task_id | str(255) nullable | Celery 任务 ID |
| error_message | text nullable | 处理失败的错误信息 |
| created_at / updated_at | datetime | 创建 / 更新时间 |
| `chunks` | one-to-many | 关联的 DocumentChunk 列表 |
| `owner` | relationship | 关联 User 对象 |

**文档状态机：** `queued` → `processing` → `ready`（成功）/ `failed`（失败）

#### `DocumentChunk` (`app/models/document.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int (PK) | 主键 |
| document_id | int (FK→documents, CASCADE) | 所属文档 |
| chunk_index | int | 块序号 |
| content | text | 文本内容 |
| embedding | Vector(1024) nullable | pgvector 向量表示 |

#### `LLMCallLog` (`app/models/llm_call_log.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int (PK) | 主键 |
| user_id | int (FK→users) nullable | 调用用户 |
| endpoint | str(100) | 调用端点 (e.g. /api/v1/chat) |
| model_name | str(100) | 使用的模型 |
| provider | str(50) | 服务商，默认 "openai_compatible" |
| request_id | str(64) nullable | 请求链路 ID |
| prompt | text | 用户输入 |
| response | text nullable | 模型回复 |
| tool_calls | text nullable | 工具调用 JSON |
| prompt_tokens / completion_tokens / total_tokens | int | Token 用量 |
| latency_ms | float | 延迟（毫秒） |
| estimated_cost_usd | float | 估算成本 |
| status | str(20) | success / failed |
| error_message | text nullable | 错误信息 |
| created_at | datetime | 创建时间，索引 |

### 5.3 服务层

#### `AuthService.authenticate_user(db, email, password)`
- 按邮箱查询用户 → 验证密码 → 返回 User 或 None
- 失败时记录 warn 级别日志

#### `UserService` 方法一览

| 方法 | 说明 |
|------|------|
| `create_user(db, user_in)` | 注册用户，检查邮箱唯一性，密码 bcrypt 哈希 |
| `get_user(db, user_id)` | 按 ID 查询用户 |
| `list_users(db)` | 所有用户列表 |
| `delete_user(db, user_id)` | 删除用户 |
| `update_llm_config(db, user_id, config_in)` | 更新 LLM 配置，API Key 使用 Fernet 加密 |
| `change_password(db, user_id, password_in)` | 修改密码（验证旧密码） |

#### `TaskService` 方法一览

| 方法 | 说明 |
|------|------|
| `create_task(db, task_in, owner_id)` | 创建任务 |
| `list_tasks(db, owner_id, skip, limit)` | 任务列表（按时间倒序） |
| `get_task(db, task_id, owner_id)` | 任务详情（校验所有权） |
| `update_task(db, task_id, owner_id, task_in)` | 更新任务（部分更新） |
| `delete_task(db, task_id, owner_id)` | 删除任务 |

#### `RAGService` 方法一览

| 方法 | 说明 |
|------|------|
| `create_document_record(...)` | 创建文档记录（状态 queued） |
| `attach_processing_task(...)` | 绑定 Celery 任务 ID |
| `process_document(document_id, task_id)` | 核心：切分 → Embedding → 入库 |
| `retrieve_relevant_chunks(query, owner_id, top_k)` | 检索：余弦距离 → reranker → Top K |
| `list_documents_for_user(owner_id)` | 用户文档列表 |
| `get_document_for_user(document_id, owner_id)` | 单文档详情（校验所有权） |
| `mark_document_processing/failed/requeue(...)` | 文档状态管理 |

### 5.4 工具函数层

#### `app.utils.encryption`

| 函数 | 说明 |
|------|------|
| `encrypt_api_key(api_key)` | 使用 Fernet (SHA-256 derived from SECRET_KEY) 加密 |
| `decrypt_api_key(encrypted_key)` | 解密 API Key，失败返回空字符串 |

#### `app.utils.errors`

| 类/函数 | 说明 |
|---------|------|
| `AppException(code, msg, status_code, data)` | 统一业务异常，携带错误码 |
| `app_exception_handler(request, exc)` | FastAPI 异常处理器，返回 `{"code", "msg", "data"}` 格式 |

#### `app.utils.file_parser`

| 函数 | 说明 |
|------|------|
| `parse_file(filename, raw_bytes)` | 自动识别文件类型并解析 (txt/md/pdf) |
| `get_supported_extensions()` | 返回支持的扩展名列表 |

#### `app.utils.rate_limit`

| 类 | 说明 |
|----|------|
| `RateLimiter(times, seconds)` | FastAPI 依赖类，基于 Redis ZSET 滑动窗口限流 |
| 降级策略 | Redis 不可用时自动放行，不影响核心业务 |

#### `app.api.middleware.RequestIDMiddleware`
- 每个请求生成 UUID，注入 `contextvars` 和 `request.state.request_id`
- 响应头返回 `X-Request-ID`

### 5.5 Celery 任务

#### `app.worker.tasks.process_document_task(document_id)`

| 步骤 | 说明 |
|------|------|
| 1 | `self.update_state(state="PROGRESS")` 回传进度 |
| 2 | 创建独立 DB Session 调用 `RAGService.process_document()` |
| 3 | 成功：更新文档状态为 ready，返回结果 |
| 4 | 失败：调用 `mark_document_failed()` 记录错误并重新抛出 |
| 5 | finally：关闭 DB Session |

### 5.6 LLM 可观测服务 (`app/services/llm_observability_service.py`)

| 函数 | 说明 |
|------|------|
| `start_timer()` | 返回 `perf_counter()` 起始时间 |
| `elapsed_ms(start_time)` | 计算从起始时间到现在的毫秒数 |
| `extract_usage(response)` | 从 OpenAI API 响应提取 prompt/completion/total tokens |
| `serialize_tool_calls(tool_calls)` | 将 tool_calls 对象序列化为 JSON |
| `estimate_cost_usd(prompt_tokens, completion_tokens)` | 根据配置单价估算成本 |
| `create_llm_call_log(...)` | 创建 LLM 调用日志记录 |
| `get_llm_overview_stats(db, user_id, days)` | 获取综合统计（total/成功/失败/token/成本/延迟 + 按天/端点/用户维度） |

---

## 6. 项目依赖说明 (Dependencies)

### 生产依赖 (`requirements.txt`)

| 包名 | 用途 |
|------|------|
| `fastapi[standard]` | 核心 Web 框架 |
| `pydantic>=2.0.0` | 数据校验与序列化 |
| `pydantic-settings>=2.0.0` | 环境变量配置加载 |
| `sqlalchemy>=2.0.0` | ORM 映射，使用 2.0 新式查询语法 |
| `psycopg[binary]>=3.1.0` | PostgreSQL 异步驱动 |
| `alembic>=1.13.0` | 数据库 Schema 迁移控制 |
| `passlib[bcrypt]>=1.7.4` | 密码哈希 |
| `bcrypt==4.0.1` | bcrypt 算法实现 |
| `PyJWT>=2.8.0` | JWT Token 签发与验证 |
| `openai>=1.12.0` | 兼容 OpenAI 标准格式的大模型 API 客户端 |
| `redis>=5.0.0` | Redis 客户端（同步 + 异步） |
| `celery>=5.3.0` | 异步任务调度框架 |
| `flower>=2.0.0` | Celery 任务监控 Web UI |
| `pgvector>=0.2.5` | PostgreSQL pgvector 扩展的 SQLAlchemy 对接 |
| `langchain-text-splitters>=0.0.1` | 长文本递归切分 |
| `python-multipart>=0.0.9` | 文件上传解析 |
| `prometheus-fastapi-instrumentator>=7.0.0` | 零侵入 API 指标采集 |
| `psutil>=5.9.0` | 系统资源监控 (CPU/内存/磁盘) |
| `cryptography>=41.0.0` | API Key 对称加解密 (Fernet) |
| `pypdf>=4.0.0` | PDF 文件文本提取 |

### 开发/测试依赖 (`requirements-dev.txt`)

| 包名 | 用途 |
|------|------|
| `pre-commit>=4.0.0` | Git hooks 管理 |
| `pytest>=8.0.0` | 测试框架 |
| `pytest-cov>=5.0.0` | 测试覆盖率报告 |
| `httpx>=0.27.0` | 异步 HTTP 客户端（TestClient 依赖） |
| `ruff>=0.3.0` | Python 代码格式化和 lint |
| `locust>=2.30.0` | 压力测试框架 |
| `fpdf2>=2.8.0` | PDF 生成（用于测试） |
| `sentence-transformers` | BGE-Reranker 重排模型（可选，运行时按需安装） |

---

## 7. 项目运行方式 (How to Run)

### 7.1 前置要求

- Docker 与 Docker Compose（推荐配合 OrbStack 获得更好的 Apple Silicon 性能）
- 如使用本地开发，需要 Python 3.9+、PostgreSQL（带 pgvector）、Redis

### 7.2 环境准备

```bash
# 复制环境变量模板
cp .env.example .env
```

**关键配置项：**
- `LLM_API_KEY`：大模型 API Key（如使用 DeepSeek / 阿里云百炼）
- `LLM_BASE_URL`：大模型 API 地址
- `LLM_MODEL_NAME`：模型名称
- `SECRET_KEY`：JWT 签名密钥，务必修改为强随机字符串
- 配置项均可在 `.env` 中按需修改

### 7.3 一键启动（推荐）

```bash
bash scripts/bootstrap_local.sh
```

该脚本自动完成：
1. 复制 `.env.example` 为 `.env`（如不存在）
2. 执行 `docker compose up -d --build` 启动所有服务
3. 等待 Ollama 就绪
4. 自动拉取 `qwen2.5:3b`（对话模型）和 `bge-m3`（向量模型）

### 7.4 手动启动

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec -T ollama ollama pull qwen2.5:3b
docker compose exec -T ollama ollama pull bge-m3
```

### 7.5 启动的服务

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| API | `fastapi-starter-api` | 8000 | FastAPI 应用 + Swagger |
| Worker | `fastapi-starter-worker` | - | Celery 异步任务处理 |
| DB | `fastapi-starter-db` | 5432 | PostgreSQL + pgvector |
| Redis | `fastapi-starter-redis` | 6379 | 缓存与消息队列 |
| Ollama | `fastapi-starter-ollama` | 11434 | 本地大模型服务 |
| Prometheus | `fastapi-starter-prometheus` | 9090 | 指标采集 |
| Grafana | `fastapi-starter-grafana` | 3000 | 监控看板 |
| Flower | `fastapi-starter-flower` | 5555 | Celery 任务监控 |

### 7.6 访问入口

| 入口 | 地址 | 说明 |
|------|------|------|
| Swagger API 文档 | http://localhost:8000/docs | 深色模式适配，支持 OAuth2 自动获取 Token |
| FastAPI Metrics | http://localhost:8000/metrics | Prometheus 指标端点 |
| 前端 Demo 页面 | http://localhost:8000/demo.html | 集成登录/RAG/聊天/任务管理 |
| 前端 SPA（开发）| http://localhost:5173 | React 开发服务器（需 `cd frontend && npm run dev`） |
| Prometheus | http://localhost:9090 | 指标查询 |
| Grafana | http://localhost:3000 | 监控看板（admin / admin） |
| Flower | http://localhost:5555 | Celery 任务监控 |

### 7.7 数据库迁移

Docker 启动时 API 容器会自动执行 `alembic upgrade head`。

手动执行：
```bash
# 生成新迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 7.8 初始化种子数据

```bash
docker compose exec api python scripts/seed_demo_data.py
```

执行后创建：
- 用户：`demo@example.com` / 密码：`demo123456`
- 欢迎文档及向量数据
- 3 个示例待办任务

### 7.9 运行测试

```bash
# 运行全部单元测试（默认使用 SQLite 内存数据库）
python3 -m pytest -q

# 使用 PostgreSQL 运行集成测试
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fastapi_db python3 -m pytest -q

# 带覆盖率报告
python3 -m pytest --cov=app --cov-report=term-missing

# RAG 端到端验证
docker compose exec api python scripts/e2e_test.py

# RAG 多格式文件上传验证
docker compose exec api python scripts/test_rag_multiformat.py

# LLM 离线评测
docker compose exec api python scripts/eval_llm_observability.py
```

### 7.10 数据库备份与恢复

```bash
# 备份
bash scripts/backup_db.sh

# 恢复
bash scripts/restore_db.sh <备份文件>
```

### 7.11 CI/CD

项目配置了 GitHub Actions 工作流（`.github/workflows/ci.yml`），在 push/PR 时自动执行：

1. **Test Job**：
   - 启动 pgvector PostgreSQL + Redis service container
   - 安装依赖并运行 `pytest`（带 coverage）
   - 上传覆盖率报告（coverage.xml）

2. **Docker Build Job**：
   - 验证 Docker 镜像构建
   - 不阻塞主流程（`continue-on-error: true`）

### 7.12 pre-commit hooks

```bash
# 安装 pre-commit hooks
pre-commit install

# 手动触发检查所有文件
pre-commit run --all-files
```

配置的 hooks：
- `ruff check` — 代码 lint
- `ruff format` — 代码格式化
- `check-yaml` / `check-json` — 格式校验
- `end-of-file-fixer` / `trailing-whitespace` — 文件格式规范

### 7.13 错误码说明

| 错误码 | 含义 | HTTP 状态码 |
|--------|------|------------|
| 1001 | 邮箱已注册 | 400 |
| 1002 | 用户不存在 | 404 |
| 1003 | JWT 凭证无效/过期 | 401 |
| 1004 | 资源不存在 | 404 |
| 1005 | 邮箱或密码错误 | 401 |
| 1006 | 用户未激活 | 400 |
| 1007 | 权限不足 | 403 |
| 1008 | 旧密码错误 | 400 |
