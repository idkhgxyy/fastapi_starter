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
