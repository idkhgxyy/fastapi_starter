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

- [ ] **RAG 支持更多文件格式**
  - 当前仅支持 `.txt`，应至少支持 `.md` 和 `.pdf`
  - 建议：引入 `PyPDF2` 或 `pdfplumber`，Markdown 可用标准库直接解析
  - 面试价值：证明不是玩具 Demo，能处理真实场景文件

- [ ] **前端 Demo 页面增强**
  - 当前 `demo.html` 只有聊天功能，缺少知识库上传 / 文档状态查看 / 任务管理
  - 建议：增加「知识库」Tab（上传文档 + 查看处理进度 + 问答）和「任务」Tab（创建/列表/状态更新）
  - 面试价值：面试官可以直接在浏览器里体验完整链路，不用 curl

- [ ] **RAG 问答支持 SSE 流式输出**
  - 当前只有 `/api/chat/` 支持 `stream=true`，RAG `/api/rag/query` 是阻塞式
  - 建议：参照 `generate_chat_reply_stream` 模式，为 RAG 增加流式回答
  - 面试价值：展示对流式协议的掌握，真实 AI 产品刚需

- [ ] **API 路径版本化**
  - 当前路由为 `/api/chat/`、`/api/rag/query` 等，建议改为 `/api/v1/...`
  - 面试价值：展示对 API 演进和兼容性的工程意识

- [ ] **Swagger UI 对接 OAuth2 自动获取 Token**
  - 当前 Swagger 页面可以填 Token，但需要手动从登录接口复制
  - 建议：在 `main.py` 中配置 `app.swagger_ui_init_oauth`，让 Swagger 自动弹出登录窗口
  - 面试价值：面试官打开 Swagger 就能直接测试所有接口

- [ ] **增加架构图和 Demo 动图到 README**
  - README 中已有 mermaid 架构图和几张截图，但缺少操作演示 GIF
  - 建议：录制一条完整的"上传文档 → 等待处理 → 知识库问答 → Agent 创建任务"操作链路的 GIF
  - 面试价值：HR 和面试官第一眼就能看懂的 Demo 比代码更有说服力

---

### 🟡 第二优先：工程健壮类（证明你具备生产级项目的思维）

- [ ] **CI 流水线增强**
  - 当前 GitHub Actions 仅跑 `pytest`，未验证 Docker 构建和 PostgreSQL 兼容性
  - 建议：增加 `docker build` 步骤 + 用 `service container` 启动 PostgreSQL 跑集成测试 + pytest-cov 覆盖率上报
  - 面试价值：展示 CI/CD 实践能力

- [ ] **修复 Ollama 容器健康检查**
  - 当前 `docker compose ps` 显示 ollama 为 `unhealthy`
  - 建议：检查 healthcheck 命令在容器内是否可用（可能需要安装 curl 或改用 wget），或延长 `start_period`
  - 面试价值：细节体现工程素养

- [ ] **Celery Worker 增加监控面板**
  - 当前 Worker 没有任何可视化监控，任务失败只能看日志
  - 建议：在 `docker-compose.yml` 中增加 `flower` 服务，端口 5555
  - 面试价值：展示对异步任务可观测性的理解

- [ ] **增加 pytest-cov 覆盖率报告**
  - 当前没有覆盖率统计，不知道测试覆盖了多少代码
  - 建议：`pip install pytest-cov`，运行 `pytest --cov=app --cov-report=term`
  - 面试价值：数据化展示测试质量

- [ ] **增加 CORS 中间件配置**
  - 当前无 CORS 配置，前端分离开发时会遇到跨域问题
  - 建议：在 `main.py` 中添加 `CORSMiddleware`，允许本地开发域名
  - 面试价值：展示对浏览器安全模型的理解

- [ ] **日志改为结构化 JSON 格式**
  - 当前日志为纯文本格式，不利于 ELK / Loki 等日志系统采集
  - 建议：使用 `python-json-logger` 或自定义 Formatter 输出 JSON
  - 面试价值：展示对云原生可观测性的理解

- [ ] **配置启动前校验**
  - 当前启动时不检查 SECRET_KEY 是否仍为默认值、LLM_API_KEY 是否为空
  - 建议：在 `lifespan` 中增加配置校验，不合规给出明确报错
  - 面试价值：防止生产事故，展示防御性编程思维

- [ ] **增加 pre-commit hooks**
  - 当前无代码格式化/Lint 自动化
  - 建议：`.pre-commit-config.yaml` 配置 black + isort + ruff
  - 面试价值：展示团队协作和代码规范意识

---

### 🟢 第三优先：功能扩展类（进一步提升项目深度，时间允许时做）

- [ ] **增加更多 Tool Calling 工具函数**
  - 当前仅 3 个工具（天气、创建任务、系统状态）
  - 建议：增加「查询任务列表」「计算器」「搜索知识库」「发送邮件」等工具
  - 面试价值：展示 Agent 工具扩展能力

- [ ] **健康检查接口增加依赖状态**
  - 当前 `GET /api/health` 仅返回 `{"ok": true}`
  - 建议：增加数据库连接状态、Redis 连接状态、Ollama 可用性检查
  - 面试价值：展示对服务健康探针的理解

- [ ] **增加用户密码修改接口**
  - 当前仅有 `PUT /me/llm-config` 修改 LLM 配置，无密码修改入口
  - 建议：`PUT /me/password`，需验证旧密码
  - 面试价值：完善用户体系

- [ ] **增加压力测试脚本**
  - 当前无性能基准
  - 建议：用 `locust` 写一个简单的并发测试脚本，验证限流和系统承载能力
  - 面试价值：展示性能意识

- [ ] **数据库备份脚本**
  - 当前无任何备份恢复方案
  - 建议：`scripts/backup_db.sh` (pg_dump) + `scripts/restore_db.sh`
  - 面试价值：运维基础

- [ ] **RAG 支持多轮对话记忆**
  - 当前每次 `/api/rag/query` 都是独立请求，无上下文记忆
  - 建议：引入对话 session 概念，Redis 存储历史 messages
  - 面试价值：展示对对话系统设计的理解

- [ ] **Embedding 维度改为可配置**
  - 当前 `DocumentChunk.embedding` 中 `Vector(1024)` 硬编码
  - 建议：从 settings 读取 `EMBEDDING_DIMENSION` 配置项
  - 面试价值：灵活性

- [ ] **增加数据初始化和 Demo 种子数据**
  - 当前启动后数据库为空，需要手动造数据
  - 建议：`scripts/seed_demo_data.py` 自动创建 demo 用户、上传文档、创建任务
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
| ✅ 单元测试 101 个 | 覆盖核心 Service/Router/Utils |
| ✅ 项目文档 | README / CODE_WIKI / MVP 文档 / 变更记录 |

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
