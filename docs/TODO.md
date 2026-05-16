# 项目待办清单 (TODO)

> 面向大二实习项目的优劣势分析与后续改进计划。
> 标记说明：🔴 高优先 / 🟡 中优先 / 🟢 低优先 / ✅ 已完成

---

## 一、项目优势总结

以下能力已经构成了一个有竞争力的实习项目：

| 类别 | 具体优势 |
|------|----------|
| **工程架构** | 严格分层架构 (API → Service → Model)，依赖注入，SQLAlchemy 2.0 新式查询语法，Alembic 数据库迁移 |
| **AI 落地** | RAG 知识库（文档上传 → 异步切分 → Embedding → pgvector 检索 → BGE-Reranker 重排）、Tool Calling（天气/任务/系统状态）|
| **安全性** | JWT + bcrypt 鉴权，cryptography 加密 API Key，用户级数据隔离，滑动窗口限流 |
| **可观测性** | Prometheus + Grafana 监控大盘，Request ID 链路追踪，LLM 调用日志（token/耗时/成本/状态）|
| **多租户** | BYOK 架构：用户可配置自有大模型厂商/Key，加密存储，优先使用用户配置 |
| **工程化** | Docker Compose 一键启动 (含 bootstrap 脚本)，单元测试 101 个，pytest + TestClient |
| **文档** | README / CODE_WIKI / MVP 文档 / 变更记录 / AI 编码约束 (CLAUDE.md) / 简历文案 |
| **代码质量** | 全面 Type Hints，统一 AppException 异常体系，结构化 Request ID 日志 |

---

## 二、待完善清单

### 🔴 第一优先：面试展示类（这些能直接提升面试官的第一印象）

- [x] **RAG 支持更多文件格式** ✅ (2026-05-14)
  - ~~当前仅支持 `.txt`，应至少支持 `.md` 和 `.pdf`~~
  - 已完成：引入 `pypdf` + `app/utils/file_parser.py`，支持 `.txt` / `.md` / `.pdf`
  - 面试价值：证明不是玩具 Demo，能处理真实场景文件

- [x] **前端 Demo 页面增强** ✅ (2026-05-14)
  - ~~当前 `demo.html` 只有聊天功能，缺少知识库上传 / 文档状态查看 / 任务管理~~
  - 已完成：重写为三栏 Tab 式布局——📚知识库Tab（多格式上传+文档状态badge+内置RAG搜索+Top-K滑块+SSE流式渲染）和📋任务Tab（创建/列表/状态循环切换/删除）
  - 面试价值：面试官可以直接在浏览器里体验完整链路，不用 curl

- [x] **RAG 问答支持 SSE 流式输出** ✅ (2026-05-14)
  - ~~当前只有 `/api/chat/` 支持 `stream=true`，RAG `/api/rag/query` 是阻塞式~~
  - 已完成：新增 `POST /api/v1/rag/query/stream` SSE流式端点，前端使用 ReadableStream 实时逐字渲染
  - 面试价值：展示对流式协议的掌握，真实 AI 产品刚需

- [x] **API 路径版本化** ✅ (2026-05-14)
  - ~~当前路由为 `/api/chat/`、`/api/rag/query` 等~~
  - 已完成：全线迁移至 `/api/v1/...`，同步更新health check、deps OAuth2 URL、前端、所有测试和脚本
  - 面试价值：展示对 API 演进和兼容性的工程意识

- [x] **Swagger UI 对接 OAuth2 自动获取 Token** ✅ (2026-05-14)
  - ~~当前 Swagger 页面可以填 Token，但需要手动从登录接口复制~~
  - 已完成：配置 `swagger_ui_init_oauth`，Swagger Authorize 弹窗直接填写邮箱密码即可自动获取Token
  - 面试价值：面试官打开 Swagger 就能直接测试所有接口

- [ ] **增加架构图和 Demo 动图到 README** ~~(已跳过)~~
  - README 中已有 mermaid 架构图和几张截图，但缺少操作演示 GIF
  - 建议：录制一条完整的"上传文档 → 等待处理 → 知识库问答 → Agent 创建任务"操作链路的 GIF（需手动录制）
  - 面试价值：HR 和面试官第一眼就能看懂的 Demo 比代码更有说服力
  - ⚠️ 用户选择跳过，当前 demo.html 已具备完整交互能力，面试官可直接在浏览器体验

---

### 🟡 第二优先：工程健壮类（证明你具备生产级项目的思维）

- [x] **CI 流水线增强** ✅ (2026-05-14)
  - ~~当前 GitHub Actions 仅跑 pytest，未验证 Docker 构建和 PostgreSQL 兼容性~~
  - 已完成：增加 `pgvector/pgvector:pg15` PostgreSQL service container 跑真实集成测试；独立 `docker-build` job 验证 Docker 构建；`pytest-cov` 覆盖率上报 + `coverage.xml` artifact 上传；`conftest.py` 支持 SQLite/PostgreSQL 双模式自动切换
  - 面试价值：展示 CI/CD 实践能力

- [x] **修复 Ollama 容器健康检查** ✅ (2026-05-15)
  - ~~当前 `docker compose ps` 显示 ollama 为 `unhealthy`~~
  - 已完成：健康检查改用容器内置 `ollama list` 命令替代不存在的 `curl`，增加 `start_period: 30s` 和 `retries: 10`
  - 面试价值：细节体现工程素养

- [x] **Celery Worker 增加监控面板** ✅ (2026-05-15)
  - ~~当前 Worker 没有任何可视化监控，任务失败只能看日志~~
  - 已完成：在 `docker-compose.yml` 中增加 `flower` 服务（端口 5555），添加 `flower>=2.0.0` 依赖
  - 面试价值：展示对异步任务可观测性的理解

- [x] **增加 pytest-cov 覆盖率报告** ✅ (2026-05-14，CI 增强子项)
  - ~~当前没有覆盖率统计，不知道测试覆盖了多少代码~~
  - 已完成：CI 中已配置 `--cov=app --cov-report=term-missing --cov-report=xml`，`requirements-dev.txt` 已添加 `pytest-cov>=5.0.0`
  - 面试价值：数据化展示测试质量

- [x] **增加 CORS 中间件配置** ✅ (2026-05-15)
  - ~~当前无 CORS 配置，前端分离开发时会遇到跨域问题~~
  - 已完成：在 `main.py` 中添加 `CORSMiddleware`，`config.py` 增加 `CORS_ORIGINS` 配置项，默认允许 localhost:3000/5173/8000
  - 面试价值：展示对浏览器安全模型的理解

- [x] **日志改为结构化 JSON 格式** ✅ (2026-05-15)
  - ~~当前日志为纯文本格式，不利于 ELK / Loki 等日志系统采集~~
  - 已完成：实现自定义 `JSONFormatter`，`config.py` 增加 `LOG_FORMAT` 配置项（text | json），`LOG_FORMAT=json` 时输出结构化 JSON 含 timestamp/level/logger/message/module/request_id/exception
  - 面试价值：展示对云原生可观测性的理解

- [x] **配置启动前校验** ✅ (2026-05-15)
  - ~~当前启动时不检查 SECRET_KEY 是否仍为默认值、LLM_API_KEY 是否为空~~
  - 已完成：在 `lifespan` 中增加 `_validate_startup_config()`，SECRET_KEY 为默认值时拒绝启动，LLM_API_KEY 为空时警告（因 BYOK 架构允许用户级配置）
  - 面试价值：防止生产事故，展示防御性编程思维

- [x] **增加 pre-commit hooks** ✅ (2026-05-15)
  - ~~当前无代码格式化/Lint 自动化~~
  - 已完成：`.pre-commit-config.yaml` 配置 ruff (lint + format) + 通用 hooks（check-yaml/check-json/end-of-file-fixer/trailing-whitespace），`pyproject.toml` 配置 ruff 规则与 pytest，`requirements-dev.txt` 添加 `pre-commit>=4.0.0`
  - 面试价值：展示团队协作和代码规范意识

---

### 🟢 第三优先：功能扩展类（进一步提升项目深度，时间允许时做）

- [x] **增加更多 Tool Calling 工具函数** ✅ (2026-05-15)
  - ~~当前仅 3 个工具（天气、创建任务、系统状态）~~
  - 已完成：新增 `list_tasks`（查询任务列表，支持状态过滤）和 `calculate`（安全计算器，仅允许数学函数），共 5 个工具
  - 面试价值：展示 Agent 工具扩展能力

- [x] **健康检查接口增加依赖状态** ✅ (2026-05-15)
  - ~~当前 `GET /api/health` 仅返回 `{"ok": true}`~~
  - 已完成：返回结构化依赖状态（database/redis/ollama），各自 status up/down + 详细信息，核心依赖异常时返回 503
  - 面试价值：展示对服务健康探针的理解

- [x] **增加用户密码修改接口** ✅ (2026-05-15)
  - ~~当前仅有 `PUT /me/llm-config` 修改 LLM 配置，无密码修改入口~~
  - 已完成：`PUT /me/password`，需验证旧密码，新密码哈希入库
  - 面试价值：完善用户体系

- [x] **增加压力测试脚本** ✅ (2026-05-15)
  - ~~当前无性能基准~~
  - 已完成：`scripts/locustfile.py` 模拟用户登录 + 健康检查/个人信息/聊天/任务列表 多场景并发，`requirements-dev.txt` 添加 `locust>=2.30.0`
  - 面试价值：展示性能意识

- [x] **数据库备份脚本** ✅ (2026-05-15)
  - ~~当前无任何备份恢复方案~~
  - 已完成：`scripts/backup_db.sh` (pg_dump + gzip) + `scripts/restore_db.sh` (gunzip + psql)，支持环境变量配置
  - 面试价值：运维基础

- [x] **RAG 支持多轮对话记忆** ✅ (2026-05-15)
  - ~~当前每次 `/api/rag/query` 都是独立请求，无上下文记忆~~
  - 已完成：`RAGQueryRequest` 新增 `session_id` 可选字段，基于 Redis 存储会话历史（最大 20 轮，1 小时 TTL），支持 `/query` 和 `/query/stream` 两个端点
  - 面试价值：展示对对话系统设计的理解

- [x] **Embedding 维度改为可配置** ✅ (2026-05-15)
  - ~~当前 `DocumentChunk.embedding` 中 `Vector(1024)` 硬编码~~
  - 已完成：`config.py` 增加 `EMBEDDING_DIMENSION: int = 1024`，`document.py` 改用 `Vector(settings.EMBEDDING_DIMENSION)`
  - 面试价值：灵活性

- [x] **增加数据初始化和 Demo 种子数据** ✅ (2026-05-15)
  - ~~当前启动后数据库为空，需要手动造数据~~
  - 已完成：`scripts/seed_demo_data.py` 创建 demo 用户 (demo@example.com / demo123456)、欢迎文档（含嵌入向量占位）、3 个示例任务
  - 面试价值：面试官一键体验完整功能

---

## 三、已具备的核心能力（维持现状即可）

以下是已经做得不错、不需要额外投入的部分：

| 已完成项 | 说明 |
|----------|------|
| ✅ JWT 鉴权体系 | 注册/登录/Token 刷新/权限校验 |
| ✅ 用户数据隔离 | RAG 文档按 owner_id 过滤，任务按用户隔离 |
| ✅ 异步文档处理 | Celery Worker 异步切分、Embedding、向量入库 |
| ✅ 限流保护 | Redis ZSET 滑动窗口限流，聊天接口 60s/20 次 |
| ✅ 可观测性 | Prometheus 指标 + Grafana 看板 + LLM 调用日志 |
| ✅ BYOK 多租户 | 用户自定义 LLM 厂商/Key，Fernet 加密存储 |
| ✅ Docker 一键启动 | docker compose up -d + bootstrap_local.sh |
| ✅ 数据库迁移 | Alembic 自动升级 |
| ✅ 统一异常处理 | AppException + 全局 handler |
| ✅ Request ID 追踪 | 中间件注入 + 响应头返回 |
| ✅ 单元测试 121 个 | 覆盖核心 Service/Router/Utils |
| ✅ 项目文档 | README / CODE_WIKI / MVP 文档 / 变更记录 |
| ✅ CI/CD 流水线 | GitHub Actions: test (PostgreSQL + pgvector) + docker-build + pytest-cov |
| ✅ CORS 跨域 | CORSMiddleware + 可配置允许域名 |
| ✅ 结构化日志 | JSONFormatter 可选 JSON 输出，适配 ELK/Loki |
| ✅ 配置校验 | 启动时检查 SECRET_KEY 等关键配置 |
| ✅ pre-commit hooks | ruff lint + format + 通用 hooks |
| ✅ 健康检查增强 | DB / Redis / Ollama 依赖状态探针 |
| ✅ 密码修改 | PUT /me/password 旧密码验证 |
| ✅ Tool Calling x5 | 天气 + 创建任务 + 系统状态 + 任务列表 + 计算器 |
| ✅ 压力测试 | locust 多场景并发脚本 |
| ✅ 数据库备份 | backup_db.sh + restore_db.sh |
| ✅ RAG 多轮对话 | session_id + Redis 历史记忆 |
| ✅ Embedding 维度可配 | EMBEDDING_DIMENSION 配置项 |
| ✅ Demo 种子数据 | seed_demo_data.py 一键初始化 |

---

## 四、评审面试视角总评

以下是从**大二实习面试官**的角度，对这个项目的整体评价：

### 加分项

1. **"不只是调 API"** — RAG 完整链路 + Tool Calling + 异步任务，比 90% 的"ChatGPT 套壳"项目强
2. **工程化意识好** — 分层架构、Alembic 迁移、Docker Compose、Prometheus 监控，不像入门 Demo
3. **安全意识及格** — API Key 加密入库，不是明文存数据库
4. **代码可维护性强** — Type Hints 全覆盖，统一异常处理，结构清晰
5. **文档齐全** — MVP 界定清晰，变更记录详尽，知道自己在做什么

### 当前最大的两个短板

1. **缺少可视化演示** — README 有截图但没有完整操作 GIF，面试官可能不会真的去跑 `docker compose up`
2. **前端体验缺失** — demo.html 功能过于基础，面试官无法在浏览器里体验 RAG + Agent 的完整链路

### 建议的补强顺序

```
第一步（本周）：录制完整 Demo GIF + 增强 demo.html（RAG 上传 + 任务管理）
第二步（下周）：API 版本化 + Swagger OAuth2 + 健康检查增强
第三步（后续）：CI 增强 + 结构化日志 + pre-commit hooks + 更多 Tool Calling
```
