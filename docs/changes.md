# 变更记录

用于记录每一轮实质性改动的目标、范围、验证方式和对应提交，方便回顾项目演进，也方便后续同步更新 `README` 和简历描述。

## 2026-05-04

### RAG 去玩具化第一轮
- 提交：`47e574f`
- 标题：`feat(rag): isolate user docs and process uploads asynchronously`
- 目标：解决“知识库不隔离用户”和“上传文档同步入库像 demo”两个核心问题。
- 主要改动：
- 为文档增加 `owner_id`、`status`、`chunks_count`、`processing_task_id`、`error_message` 等字段
- 检索时只查询当前用户且已处理完成的文档
- 上传接口改为“先落库、后投递 Celery 任务”
- Worker 改为执行真实切分、Embedding 和向量入库
- 新增文档列表与单文档状态查询接口
- 新增数据库迁移：`5c6f8b7a9d21_add_document_ownership_and_status.py`
- 验证：
- `python3 -m pytest -q tests/test_rag.py tests/test_auth.py tests/test_users.py tests/test_health.py`

### RAG 去玩具化第二轮
- 提交：`7c67824`
- 标题：`refactor(rag): harden document processing workflow`
- 目标：补齐文档处理失败标记、重处理入口、任务状态查询和展示细节。
- 主要改动：
- 保留并兼容 `BGE-Reranker` 可选重排逻辑
- `worker/process` 只允许当前用户重处理自己的文档
- `worker/status/{task_id}` 仅允许查询当前用户自己的文档任务
- 上传失败时回写文档失败状态和错误信息
- 清理旧注释，并修复 `Task` schema 的 Pydantic v2 配置写法
- 补充 RAG/Worker 相关自动化测试
- 验证：
- `python3 -m pytest -q`

### 文档同步
- 目标：让仓库文档与当前实现保持一致，避免“代码改了但 README 还是旧的”。
- 主要改动：
- 更新 `README.md` 中 RAG 亮点、接口示例、测试命令和最近更新说明
- 新增本文件，用于后续持续记录每轮改动

### 文档同步第二轮
- 提交：本轮 `docs` 同步提交
- 目标：让 MVP 文档和简历文案与当前实现完全对齐。
- 主要改动：
- 更新 `docs/project_mvp.md`，突出用户隔离的知识库、真实异步处理、文档状态查询和重处理链路
- 更新 `docs/resume_project.md`，强化“按用户隔离的 RAG”“真实异步文档处理”“可选 reranker”“自动化测试覆盖”等卖点
- 更新 `docs/resume_project_final_short.md`，让压缩版简历描述与当前实现一致

## 维护约定
- 每次一轮实质性代码改动后，必须同步更新 `README.md`
- 每次都要在本文件追加一条记录，至少写明：目标、主要改动、验证方式、对应提交
- 如果一次改动拆成多次提交，记录里保留所有关键提交号

## 2026-05-09

### 引入全局 AI 编码约束文件
- 目标：随着项目复杂度提升，规范后续 AI 辅助编码（如 Trae, Claude, Cursor）的行为，防止破坏架构设计和编码规范。
- 主要改动：
  - 新增 `CLAUDE.md` 文件，定义了项目分层原则、编码风格（如 SQLAlchemy 2.0 语法、Type Hints）、数据库迁移强制流程以及文档同步约束。
  - 更新 `README.md` 维护约定，加入对 AI 辅助开发的说明。

### 新增完整的 Code Wiki 文档
- 目标：提供结构化、清晰的项目整体架构、模块职责和代码运行指南，方便后续开发与回顾。
- 主要改动：
  - 新增 `docs/CODE_WIKI.md`，包含项目架构、技术栈、核心模块逻辑说明以及主要类和函数的详细解析。
  - 在 `README.md` 的目录结构部分增加了指向 `CODE_WIKI.md` 的指引链接。

### 新增轻量级前端 Demo 页面
- 目标：补齐项目 MVP 阶段缺乏前端展示页面的短板，方便在简历或面试演示中提供更直观的交互体验。
- 主要改动：
  - 新增 `app/static/demo.html`，采用 TailwindCSS 构建，支持深色模式。
  - 在 `app/main.py` 中通过 `StaticFiles` 挂载静态目录，可通过 `http://localhost:8000/demo.html` 访问。
  - 页面集成了 JWT Token 认证配置、RAG 知识库上传与状态轮询、以及 AI 聊天对话功能。

### Agent 工具扩展：系统状态查询
- 目标：让 Agent 具备更强的系统可观测性与运维查询能力，体现真正的 Backend Tool Calling。
- 主要改动：
  - 在 `requirements.txt` 中引入 `psutil` 依赖，并执行安装。
  - 在 `app/services/llm_service.py` 中新增 `get_system_status` 本地工具函数，可获取 CPU、内存及磁盘的真实负载情况。
  - 新增 `SYSTEM_STATUS_TOOL` JSON Schema 并在大模型调用中注入该工具，实现自然语言查询服务器状态。
