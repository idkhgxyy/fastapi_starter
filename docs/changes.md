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

### 评测与工程化：限流、SSE及离线评测扩充
- 目标：完善系统的流式输出能力、接口限流保护以及离线评测集，证明系统的健壮性和可观测性。
- 主要改动：
  - 在 `app/utils/rate_limit.py` 中基于 Redis ZSET 实现滑动窗口限流器，并在 `app/api/routers/chat.py` 中为聊天接口挂载了 `60 秒内 20 次请求` 的限制。
  - 修改 `app/schemas/chat.py` 和 `app/services/llm_service.py`，新增 `generate_chat_reply_stream` 支持真正的 SSE 流式输出，客户端可传入 `stream=True` 获取流式响应。
  - 扩充了 `scripts/eval_llm_observability.py` 离线评测集，增加了对“系统状态查询”、“工具组合”及“拒绝不合理要求”等复杂指令的自动化评测。
  - 补充了 `tests/test_chat_advanced.py`，使用 `unittest.mock` 对限流规则与 SSE 流式返回格式进行了自动化单元测试。

### 架构演进：多租户 LLM 自定义配置 (BYOK)
- 目标：将项目升级为商业级 SaaS 架构，允许不同租户在前端独立配置自己的大模型服务商及 API Key，并提供加密存储保障安全。
- 主要改动：
  - 引入 `cryptography` 依赖，并在 `app/utils/encryption.py` 中基于项目 `SECRET_KEY` 派生出 Fernet 密钥对用户输入的 API Key 进行对称加解密。
  - 修改 `User` 模型与数据库表（通过 Alembic 生成并执行了新迁移），新增 `llm_provider`、`llm_base_url`、`llm_model_name` 及 `llm_api_key_encrypted` 字段。
  - 在 `app/api/routers/users.py` 新增了 `PUT /me/llm-config` 接口，并在前端 `demo.html` 页面增加了「模型配置」模态框面板，供用户动态切换 OpenAI、DeepSeek 等兼容大模型。
  - 重构了 `llm_service.py` 中的 `get_llm_client` 方法，实现对当前登录用户的个性化配置读取，未配置时则优雅降级为系统全局 LLM 配置。

## 2026-05-14

### 测试覆盖大幅扩充
- 提交：`46d14f4`
- 标题：`test: add 88 new unit tests and e2e verification script`
- 目标：将测试从 13 个扩充到 101 个，覆盖 encryption、security、errors、task CRUD、RAG service、observability、LLM tools、user/auth service 等核心模块。
- 主要改动：
  - 新增 `tests/test_encryption.py`（9 个）、`test_security.py`（11 个）、`test_errors.py`（6 个）、`test_task_endpoints.py`（14 个）、`test_rag_service.py`（16 个）、`test_observability.py`（13 个）、`test_llm_tools.py`（9 个）、`test_user_service_direct.py`（7 个）、`test_auth_service.py`（3 个）
  - 新增 `scripts/e2e_test.py` 端到端验证脚本（12 步）
- 验证：`python3 -m pytest -q` → 101 passed

### 项目 TODO 清单
- 提交：`735aa71`
- 标题：`docs: add comprehensive TODO list with project strengths/weaknesses analysis`
- 目标：系统分析项目优劣势，规划后续改进路线图。
- 主要改动：
  - 新增 `docs/TODO.md`，含优势总结、22 项待完善清单（按优先级分三档）、面试视角评审

### RAG 多格式文件上传（.md / .pdf）
- 提交：`7a8b9b0`
- 标题：`feat(rag): support .md and .pdf file uploads alongside .txt`
- 目标：完成 TODO 清单第一优先第一项——RAG 支持更多文件格式。
- 主要改动：
  - 新增 `app/utils/file_parser.py`：统一文件解析器，支持 `.txt` / `.md` / `.pdf`，基于 `pypdf` 做 PDF 文本提取
  - `Document` 模型新增 `file_type` 字段（默认 `"txt"`），Alembic 迁移 `b35f62ae79bf`
  - `DocumentResponse` Schema 新增 `file_type` 字段
  - 上传接口重构：接受 `.txt` / `.md` / `.markdown` / `.pdf`，拒绝其他格式
  - 新增 sample 文件：`sample_knowledge.md`、`sample_knowledge.pdf`
  - 新增 `tests/test_file_parser.py`（14 个文件解析测试）
  - 补充 `test_rag.py` 中 .md/.pdf 上传、不支持格式拒绝、空 PDF 拒绝 4 个测试
  - 新增 `scripts/test_rag_multiformat.py` live API 多格式验证脚本
- 验证：
  - `python3 -m pytest -q` → 119 passed
  - Live API: .txt / .md / .pdf 上传均返回 202 + 正确 file_type，.png 返回 400

## 2026-05-28 ~ 2026-05-29

### 全功能 React SPA 前端
- 目标：为后端构建一个完整的现代化前端界面，覆盖后端全部 API 端点，提供面试级的前端代码质量。
- 主要改动：
  - 新建 `frontend/` 目录，基于 Vite 8 + React 18 + TypeScript strict 模式
  - Tailwind CSS v4 + CSS 变量双主题体系（深色/浅色）
  - 8 个独立路由页面：`/auth/login`、`/auth/register`、`/chat`、`/knowledge`、`/tasks`、`/observability`、`/settings`、`/health`
  - **Chat 核心**：SSE 流式渲染（fetch + ReadableStream）、useChat Hook、MessageList（Markdown/推理折叠/ToolCallCard）、自动增高 ChatInput
  - **侧边栏**：抽屉式布局（桌面/移动端均可折叠）、知识库面板（上传文档/列表/删除/RAG搜索）、任务面板（创建/状态切换/删除）
  - **可观测性面板**：Recharts 折线图/柱状图、统计卡片、LLM 调用日志表格 + 详情 Modal
  - **Mock 数据层**：`VITE_USE_MOCK=true` 切换，axios 请求拦截器级别模拟，零网络请求零错误日志
  - **全局 ErrorBoundary** 包裹应用
  - 7 个 API Service、2 个 Context（Auth/Theme）、18 个 SVG 图标组件
  - 设计体系：Plus Jakarta Sans + JetBrains Mono 字体、品牌色 indigo (#6366f1)、surface 灰度色板
  - CLAUDE.md 同步新增前端设计准则
- 验证：`npx tsc --noEmit` → 0 errors, `npx vite build` → 920 modules 构建通过

## 2026-06-08

### README 面试官视角优化
- 目标：移除 README 中对面试官暴露的面试准备内容和内部开发流程。
- 主要改动：
  - 重写开头描述为专业英文一句话简介，移除"面向实习/校招场景"等自曝式措辞
  - 删除"适合怎么写进简历"板块（含简历定位建议和 `resume_project.md` 链接）
  - 删除"后续可继续优化"板块（暴露项目未完成的 roadmap）
  - 删除"维护约定"板块（内部开发流程文档）
  - 新增"About This Project"板块，用英文专业方式总结核心能力
- 验证：文件完整性检查通过

### 文档清理与整合
- 目标：清理 docs/ 目录中的过期和冗余文档，使文档与当前项目状态（含完整 React SPA 前端 + MCP 协议层）对齐。
- 主要改动：
  - **删除** `docs/TODO.md`：所有 22 项待办已全部完成，内容与 PROJECT_REVIEW.md 重叠
  - **删除** `docs/resume_project_final_short.md`：内容已合并入 `resume_project.md`
  - **删除** `docs/IMPROVEMENT_SUGGESTIONS.md`：95% 建议已落地，剩余条目为次要意见
  - **更新** `docs/resume_project.md`：合并压缩版内容，新增"全栈"定位，体现 React 前端和 MCP 协议
  - **更新** `docs/PROJECT_REVIEW.md`：修正"缺少前端/Demo 简陋"等过期评价；标注已完成的改进项
  - **更新** `docs/CODE_WIKI.md`：新增 `frontend/` 目录结构、`mcp_service.py` 模块文档、前端访问入口
  - **更新** `docs/project_mvp.md`：将已实现的"前端/BYOK/SSE/MCP"从"不必强求"移至"已超出 MVP"
  - **更新** `docs/FRONTEND_PRD.md`：顶部添加历史文档标注
  - **更新** `README.md`：移除对已删除文件的引用
- 验证：所有引用一致性检查通过
