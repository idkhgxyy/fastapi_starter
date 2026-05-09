# FastAPI Starter - Code Wiki

## 1. 项目概述 (Project Overview)

本项目是一个功能完善的 FastAPI 生产级脚手架，核心业务目标是打造**个人知识库 + 任务执行 Agent**。项目不仅仅是一个简单的 CRUD 后端，还集成了大模型（LLM）对话、工具调用（Tool Calling）、检索增强生成（RAG）、异步任务处理以及可观测性（Observability）等高级特性。

### 核心特性
*   **LLM Agent 与工具调用**：支持流式对话（SSE），基于本地或远端大模型（推荐使用 Qwen2.5 等能力较强的模型），支持通过 Tool Calling 拦截用户意图并执行本地方法（如天气查询、自动创建任务）。
*   **RAG 知识库检索**：集成 `pgvector` 向量数据库与 LangChain 文本切分器，实现文档上传、分块、Embedding 向量化以及基于 `BGE-Reranker` 的高精度交叉重排。
*   **异步任务与队列**：基于 Celery + Redis 实现耗时任务（如文档解析、向量化）的后台处理。
*   **鉴权与权限**：基于 JWT 的认证体系，使用 bcrypt 进行密码哈希，支持多租户数据隔离。
*   **可观测性体系**：集成 `prometheus-fastapi-instrumentator` 收集 API 指标，通过 Grafana 提供可视化看板；并在数据库中落表记录 LLM 调用的详细日志（Token 消耗、延迟、成功率等）。

---

## 2. 项目整体架构 (Overall Architecture)

本项目遵循典型的**分层架构（Layered Architecture）**，并通过 Docker Compose 进行容器化编排。

### 技术栈
*   **Web 框架**: FastAPI + Pydantic (参数校验与序列化)
*   **数据库**: PostgreSQL (带 pgvector 扩展) + SQLAlchemy ORM + Alembic (数据库迁移)
*   **缓存与消息中间件**: Redis
*   **异步调度**: Celery
*   **大模型基座**: 兼容 OpenAI API 的客户端 (可用 Ollama 本地部署或接入云端 API)
*   **监控看板**: Prometheus + Grafana

### 运行拓扑
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
                ▼      │
             [ Redis ] ◄──────────────► [ LLM Service (Ollama / Qwen2.5) ]
```

---

## 3. 目录结构说明 (Directory Structure)

```text
fastapi_starter/
├── app/
│   ├── api/            # 控制器层 (Controllers/Routers)
│   │   ├── routers/    # 按业务划分的路由 (auth, chat, rag, tasks, users, worker)
│   │   ├── deps.py     # FastAPI 依赖注入 (如获取 DB session、获取当前用户)
│   │   └── middleware.py # 自定义中间件 (如 RequestID 注入)
│   ├── core/           # 核心配置
│   │   ├── config.py   # Pydantic BaseSettings 环境变量加载
│   │   ├── security.py # JWT 签发与密码哈希校验
│   │   └── logging.py  # 日志配置
│   ├── db/             # 数据库连接与基类
│   │   ├── base.py     # SQLAlchemy Base
│   │   └── session.py  # engine 与 SessionLocal 初始化
│   ├── models/         # 领域数据模型 (SQLAlchemy ORM)
│   │   ├── user.py, task.py, document.py, llm_call_log.py
│   ├── schemas/        # 数据传输对象 (Pydantic DTOs)
│   ├── services/       # 业务逻辑层 (Services) - 核心业务处理
│   │   ├── auth_service.py, llm_service.py, rag_service.py, task_service.py, etc.
│   ├── utils/          # 工具类与全局异常处理 (errors.py)
│   ├── worker/         # Celery 任务定义与配置
│   │   ├── celery_app.py
│   │   └── tasks.py
│   └── main.py         # FastAPI 实例入口与生命周期管理
├── alembic/            # 数据库迁移脚本目录
├── docs/               # 项目文档与设计说明
├── grafana/            # Grafana 仪表盘与数据源预配置
├── tests/              # Pytest 单元测试
├── docker-compose.yml  # 容器编排文件
├── Dockerfile          # 后端服务镜像构建文件
├── requirements.txt    # 项目生产依赖
└── prometheus.yml      # Prometheus 抓取配置
```

---

## 4. 主要模块职责 (Main Modules Responsibilities)

### 4.1 LLM & Agent 模块 (`app/services/llm_service.py` & `chat.py`)
*   **职责**：处理与大模型的交互对话，封装工具定义（JSON Schema），解析模型响应中的 `tool_calls`。
*   **特性**：内置多轮调用逻辑。当大模型决定使用工具（如 `create_task`）时，拦截请求调用 `TaskService` 写入数据库，再将工具执行结果组装成 Context 投喂给大模型进行第二轮生成。

### 4.2 RAG 模块 (`app/services/rag_service.py` & `rag.py`)
*   **职责**：实现文档的检索增强生成能力。
*   **流程**：
    1. 接收文件，创建文档记录。
    2. 使用 `RecursiveCharacterTextSplitter` 进行文本分块。
    3. 调用 Embedding API 进行批量向量化。
    4. 存入 PostgreSQL (`DocumentChunk` 表，存储 `pgvector` 向量)。
    5. **检索优化**：查询时先计算余弦距离召回 top `K*3` 候选块，再使用 `CrossEncoder(BAAI/bge-reranker-base)` 交叉编码器进行精确算分重排，返回最相关的 Top K。

### 4.3 异步任务模块 (`app/worker/tasks.py`)
*   **职责**：将阻塞的重负载任务剥离出主线程。
*   **关联**：目前 RAG 文档切分与向量化等长耗时操作会通过 Celery 分发给 Worker 异步执行，保证 API 的极速响应。

### 4.4 任务管理模块 (`app/services/task_service.py`)
*   **职责**：管理用户个人的 Todo List，提供标准的 CRUD 操作。通过依赖注入实现数据基于 `owner_id` 的租户隔离。

---

## 5. 关键类与函数说明 (Key Classes & Functions)

### `app.main.lifespan`
*   **类型**: FastAPI 异步上下文管理器
*   **说明**: 在应用启动时执行初始化逻辑（如测试 PostgreSQL 连接可用性），并在应用关闭时进行清理。

### `app.services.llm_service.generate_chat_reply`
*   **参数**: `message: str, db: Session, current_user_id: int`
*   **说明**: 核心 Agent 执行引擎。
    *   **Round 1**: 携带系统 Prompt 与 Tools (如天气查询、创建任务) 请求 LLM。
    *   **Tool Execution**: 解析 `response_message.tool_calls`，在本地反射执行具体业务代码，如 `TaskService.create_task`。
    *   **Round 2**: 组装 Tool 执行结果，再次请求大模型生成自然语言回复。
    *   **日志记录**: 在流转末尾调用 `create_llm_call_log` 记录请求与 Token 消耗。

### `app.services.rag_service.RAGService.process_document`
*   **说明**: 执行文档的后处理流程。清空旧 Chunk，将全文本按指定大小分块，批量请求 Embedding 接口，最后批量落库（`db.add_all(db_chunks)`）。

### `app.services.rag_service.RAGService.retrieve_relevant_chunks`
*   **说明**: RAG 的核心召回与排序函数。先在数据库层面用 `order_by(DocumentChunk.embedding.cosine_distance(query_vector))` 完成初筛，再通过 `_predict_rerank_scores` 调用本地加载的 BGE 模型计算相似度得分，最终倒序排列返回。

---

## 6. 项目依赖说明 (Dependencies)

核心依赖包位于 `requirements.txt`：
*   **`fastapi[standard]`**: 核心 Web 框架。
*   **`sqlalchemy` & `alembic` & `psycopg[binary]`**: ORM 映射及同步/异步 PostgreSQL 驱动，Alembic 负责数据库 Schema 迁移控制。
*   **`pgvector`**: SQLAlchemy 对接 Postgres Vector 的扩展包，支持向量存取与距离计算。
*   **`openai`**: 用于对接任何兼容 OpenAI 标准格式的大模型 API（含 Ollama 本地部署、阿里云千问等）。
*   **`PyJWT` & `passlib[bcrypt]`**: 处理 JWT Token 鉴权以及用户密码的安全哈希。
*   **`celery` & `redis`**: 异步任务的调度中心与后端存储/消息代理。
*   **`langchain-text-splitters`**: 提供高效可靠的长文本切分工具。
*   **`prometheus-fastapi-instrumentator`**: 零侵入收集 API QPS、延迟、HTTP 状态码等指标。

---

## 7. 项目运行方式 (How to Run)

建议使用 Docker Compose (推荐结合 OrbStack) 进行一键部署启动。

### 7.1 环境准备
复制环境变量文件模板并按需修改：
```bash
cp .env.example .env
```
> **注意**: 请在 `.env` 中正确配置 `LLM_API_KEY` 和 `LLM_BASE_URL` (如使用 Qwen2.5-72B-Instruct API)。

### 7.2 启动服务
在项目根目录执行：
```bash
docker-compose up -d --build
```
该指令将启动以下容器：
1.  **API 服务** (`fastapi-starter-api`): 端口 8000
2.  **Celery Worker** (`fastapi-starter-worker`): 负责后台任务
3.  **PostgreSQL 数据库** (`fastapi-starter-db`): 端口 5432
4.  **Redis** (`fastapi-starter-redis`): 端口 6379
5.  **Ollama** (`fastapi-starter-ollama`): 端口 11434 (可选本地模型服务)
6.  **Prometheus & Grafana**: 端口 9090 & 3000

### 7.3 访问入口
*   **Swagger API 文档**: [http://localhost:8000/docs](http://localhost:8000/docs) (已做深色模式适配)
*   **Grafana 监控看板**: [http://localhost:3000](http://localhost:3000) (默认账号密码: `admin` / `admin`)

### 7.4 数据库迁移
Docker 启动时 API 容器会自动执行 `alembic upgrade head`，如需手动修改数据库模型，可进入容器或在本地环境中执行：
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```
