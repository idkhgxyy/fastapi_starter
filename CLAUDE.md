# AI Agent / Claude 辅助开发指南

此文档旨在为参与本项目的 AI 辅助编程工具（如 Claude, Cursor, Trae 等）提供全局上下文与编码约束。在生成代码或分析项目时，请务必严格遵守以下规则。

## 1. 核心架构与分层原则

本项目遵循严格的职责分离（Separation of Concerns）架构。

*   **API 层 (`app/api/routers/`)**: 仅负责接收 HTTP 请求、参数校验（依赖 Pydantic Schema）和返回响应。**绝对禁止**在 Router 中直接编写复杂的业务逻辑或数据库操作。
*   **服务层 (`app/services/`)**: 存放所有的核心业务逻辑。Router 必须调用 Service 层的方法来处理业务。
*   **数据模型 (`app/models/`)**: 仅存放 SQLAlchemy ORM 模型定义。
*   **数据结构 (`app/schemas/`)**: 仅存放 Pydantic 验证模型，用于 API 请求与响应的序列化/反序列化。
*   **异步任务 (`app/worker/`)**: 所有耗时操作（如大文件切分、批量向量化、发邮件等）必须通过 Celery Task 异步执行，不要阻塞 FastAPI 主线程。

## 2. 编码风格与规范

*   **类型提示 (Type Hints)**: 所有函数、方法签名必须包含严格的类型提示。例如 `def get_user(user_id: int) -> Optional[User]:`。
*   **异常处理**: 统一抛出 `app.utils.errors.AppException`，并在其中指定错误码和 HTTP 状态码。不要直接抛出 `HTTPException`。
*   **数据库操作**:
    *   统一通过依赖注入 (`app.api.deps.get_db`) 获取数据库 `Session`。
    *   使用 SQLAlchemy 2.0 风格的查询语法（如 `select()`, `execute().scalars().all()`），避免使用已废弃的 1.x 语法（如 `session.query(User).filter(...)`）。
*   **日志记录**: 使用 `app.core.logging.logger` 记录关键业务节点和异常信息，禁止使用 `print()`。

## 3. 修改数据库结构时的强制流程

如果你修改了 `app/models/` 目录下的任何模型（新增表、新增字段、修改字段类型等），你**必须**提醒用户或自动生成 Alembic 迁移脚本：

1.  确保模型已在 `app/models/__init__.py` 中导入。
2.  执行：`alembic revision --autogenerate -m "describe_your_changes"`
3.  审查生成的迁移脚本。
4.  执行：`alembic upgrade head`

## 4. 依赖管理

*   如果引入了新的第三方库，必须将其添加到 `requirements.txt` 中。
*   开发/测试相关的依赖应添加到 `requirements-dev.txt` 中。

## 5. RAG 与 LLM 相关逻辑

*   **Tool Calling**: 在 `llm_service.py` 中新增工具时，必须同时定义严格的 JSON Schema，并在执行后将结果正确 append 回对话历史。
*   **向量库**: 与 `pgvector` 相关的查询必须确保维度匹配，并在必要时考虑索引优化（如 HNSW 索引）。

## 6. 文档同步约束

当完成一次具有实质性的功能开发、重构或架构调整后，你**必须**：
1.  更新 `docs/changes.md`，记录本次修改的目标、改动内容和相关验证。
2.  如果影响了项目启动或核心架构，必须同步更新 `README.md` 和 `docs/CODE_WIKI.md`。

## 7. 测试驱动

*   任何核心业务逻辑的修改或新增，应尽量伴随单元测试的补充。
*   测试代码存放在 `tests/` 目录下，使用 `pytest` 框架。
*   运行测试前确保不依赖生产数据库数据，使用测试专用的配置或 mock。

## 8. 前端设计准则 (frontend-design skill)

编写任何前端代码时，必须遵循以下设计哲学：

### 8.1 设计定位
本项目走 **Refined Minimalism**（精致克制）路线。用户是开发者，核心诉求是信息清晰、操作高效、运行流畅。**不搞花哨的营销视觉**，但每个细节都要经得起推敲。

### 8.2 Typography
- 拒绝 Inter、Roboto、Arial 等泛用字体。选择有质感的字体组合：
  - 代码/数据展示 → JetBrains Mono / IBM Plex Mono
  - 正文/UI → 一套优雅的无衬线体（如 Satoshi、Plus Jakarta Sans、Onest 等）
- 用 font-weight 和 letter-spacing 传递层次感，不要过多依赖 color

### 8.3 Color & Theme
- **深色主题为主**（AI 工具默认深色），同时支持浅色主题跟随系统
- 品牌色做**点睛之笔**（发送按钮、状态指示灯、链接），不喧宾夺主
- 用 CSS 变量驱动所有颜色，保持一致性
- 避免千篇一律的紫+白渐变配色

### 8.4 动效
- **关键位置发力**，不做零散的小动画：
  - SSE 流式文本的逐字出现 → 打字机效果
  - 发送消息后滚动到最新消息 → smooth scroll
  - Tool Calling 卡片展开/折叠 → 轻量 transition
  - 页面入场 → 一次有节奏的 staggered reveal
- 优先使用 CSS transition/animation，React 组件用 Motion 库

### 8.5 布局
- 保持 PRD 定义的三栏结构：Navbar + Sidebar(320px) + ChatArea
- 不对称布局本身就是辨识度，不需要额外"搞艺术"
- 响应式断点：<768px(移动端隐藏侧边栏) / 768~1024(侧边栏可折叠) / >1024(完整三栏)

### 8.6 背景与氛围
- 聊天区域可以用微妙的渐变或噪点纹理增加质感
- 统计表格、日志列表这些信息密集型区域必须**干净清晰**，不加多余装饰
- 卡片用 subtle border + 恰到好处的 shadow，别用毛玻璃（会干扰大量文本阅读）

### 8.7 核心原则
- 不要让用户觉得"这个页面好花哨"，而要让他们觉得"这个工具好精致好用"
- 每个组件不超过 200 行，保持一致的文件命名规范
- TypeScript 严格模式，禁止 `any`

## 9. 任务执行策略（强制）

*   **大任务拆成小任务**：任何涉及多个文件或多种功能的改动，必须先拆分为独立的子任务，使用 TodoWrite 追踪。
*   **每步只做一个子任务**：一次只修改一种功能。完成一个子任务 → 验证 → 再进入下一个。禁止在一次聊天中试图重写整个文件。
*   **增量修改优于重写**：修改 HTML/前端文件时，只 SearchReplace 需要改的部分，不要 Write 整个文件。大文件重写极易被 SSE 截断。
*   **每次修改后验证**：改了后端代码就跑 `pytest`，改了前端代码就检查文件完整性（`wc -l` + `tail`）。
*   **不确定就先排查**：用户报告 Bug 时，先用 curl / docker logs 复现和定位根因，确认后再改。不要猜。
