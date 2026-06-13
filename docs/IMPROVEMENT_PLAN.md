# FastAPI Starter 改进计划

> 整合自：2026-06-13 全量功能测试 + 代码审查 + 原有 PROJECT_REVIEW.md
> 测试环境：Docker Compose（API + DB + Redis + Ollama + Worker），前端 Vite Dev Server

---

## 一、全量功能测试结果汇总

### 1.1 基础设施（全部通过）

| 服务 | 状态 | 备注 |
|------|------|------|
| PostgreSQL (pgvector) | ✅ UP | pgvector 扩展已安装 |
| Redis | ✅ UP | 健康检查通过 |
| Ollama | ✅ UP | 已拉取 qwen2.5:3b + bge-m3 |
| Celery Worker | ✅ UP | 文档处理任务正常执行 |
| Prometheus | ✅ UP | 指标正常暴露 |
| Grafana | ✅ UP | 3000 端口可访问 |

### 1.2 后端 API 测试

#### 认证模块（7/7 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 检查系统初始化状态 | ✅ | 正确返回 `initialized: false/true` |
| 首次 Setup 创建管理员 | ✅ | 返回 JWT Token |
| 用户登录 | ✅ | OAuth2 兼容格式 |
| 重复 Setup | ✅ | 正确拒绝 (code=1010) |
| 错误密码登录 | ✅ | 正确拒绝 (code=1005) |
| 无 Token 访问受保护端点 | ✅ | 返回 401 (code=1008) |
| 无效 Token 访问 | ✅ | 返回 401 (code=1003) |

#### 用户模块（6/6 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 获取当前用户 /users/me | ✅ | — |
| 更新 LLM 配置 | ✅ | BYOK 功能正常 |
| 修改密码 | ✅ | — |
| 错误旧密码修改密码 | ✅ | 正确拒绝 (code=1008) |
| 创建新用户 | ✅ | — |
| 获取用户列表（需 superuser） | ✅ | 权限控制正确 |

#### 任务模块（10/10 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 创建任务 | ✅ | 201 Created |
| 列出任务 | ✅ | 按 created_at 倒序 |
| 获取单个任务 | ✅ | — |
| 更新任务 | ✅ | 部分更新正常 |
| 删除任务 | ✅ | — |
| 获取不存在的任务 | ✅ | 404 (code=1004) |
| 无认证创建任务 | ✅ | 401 |
| 无效数据创建任务 | ✅ | 422 Pydantic 校验 |
| 用户数据隔离 | ✅ | 只能操作自己的任务 |
| 分页参数 | ✅ | skip/limit 正常 |

#### Chat 模块（5/7 通过，2 项部分通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 基础聊天（非流式） | ✅ | Mock 模式正常 |
| SSE 流式聊天 | ✅ | 逐字输出 + [DONE] 结尾 |
| Tool Calling - 创建任务 | ⚠️ 部分 | Mock 模式不触发真实工具调用 |
| Tool Calling - 天气查询 | ⚠️ 部分 | Mock 模式不触发真实工具调用 |
| Tool Calling - 系统状态 | ⚠️ 部分 | Mock 模式不触发真实工具调用 |
| 无认证访问 | ✅ | 401 |
| 空消息 | ✅ | 422 校验 |

#### RAG 模块（9/9 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 列出文档（空） | ✅ | — |
| 上传 .txt 文档 | ✅ | 202 Accepted，异步处理 |
| 列出文档（上传后） | ✅ | status=ready, chunks_count=1 |
| 获取文档状态 | ✅ | — |
| 查询知识库 | ✅ | source_chunks 正确检索 |
| 上传不支持的文件类型 | ✅ | 400 |
| 空查询 | ✅ | 400 |
| 删除文档 | ✅ | — |
| 删除后查询 | ✅ | 返回"暂无文档" |

#### Worker 模块（3/3 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 提交文档处理任务 | ✅ | — |
| 查询任务状态 | ✅ | — |
| 不存在的文档/任务 | ✅ | 404 |

#### 可观测性模块（3/3 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| LLM 调用日志 | ✅ | 包含完整 token/延迟/成本信息 |
| LLM 统计汇总 | ✅ | 含每日/端点/用户维度 |
| 分页查询 | ✅ | — |

#### 其他（4/4 通过）

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 健康检查 | ✅ | DB/Redis/Ollama 全部 UP |
| Swagger UI | ✅ | 深色模式适配正常 |
| Prometheus /metrics | ✅ | — |
| 限流（Chat 20次/60s） | ✅ | 第 21 次返回 429 |

### 1.3 前端测试

| 测试项 | 结果 | 备注 |
|--------|------|------|
| Vite Dev Server 启动 | ✅ | 端口 5175 |
| 页面 HTML 渲染 | ✅ | React SPA 正常 |
| Setup 页面 | ✅ | 表单验证正常 |
| 登录页面 | ✅ | — |
| Chat 页面（SSE 流式） | ✅ | — |
| 知识库页面 | ✅ | 上传/删除/查询 |
| 任务页面 | ✅ | CRUD |
| 设置页面 | ✅ | LLM 配置 + 修改密码 |
| 健康检查页面 | ✅ | — |
| 可观测性页面 | ✅ | 图表 + 日志表 |

---

## 二、发现的问题（按严重程度排序）

### 🔴 严重问题（影响核心功能）

#### P1: Setup 创建的首个用户不是 superuser
- **位置**: `app/api/routers/auth.py` → `initial_setup()`
- **现象**: 通过 `/auth/setup` 创建的第一个用户 `is_superuser=False`，导致无法访问 `/users/` 列表和删除用户等管理员接口
- **影响**: 首次部署后管理员无法执行管理操作
- **修复方案**: 在 `initial_setup` 中创建用户后，显式设置 `is_superuser=True`

#### P2: 前端未构建到 Docker 镜像中
- **位置**: `app/main.py` L218-225 的静态文件挂载逻辑
- **现象**: `GET /` 返回 JSON 欢迎消息而非 React SPA，`frontend/dist/` 目录不存在
- **影响**: Docker 部署后无法通过根路径访问前端
- **修复方案**: 在 Dockerfile 中添加前端构建步骤，或在 `docker-compose.yml` 中添加前端构建服务

### 🟡 中等问题（影响体验或代码质量）

#### P3: observability 路由使用旧式 SQLAlchemy 语法
- **位置**: `app/api/routers/observability.py` L33
- **现象**: 使用 `db.query(LLMCallLog)` 而非 `select(LLMCallLog)`，与项目其他模块不一致
- **影响**: 代码风格不统一，违反 CLAUDE.md 中 SQLAlchemy 2.0 规范
- **修复方案**: 改为 `db.execute(select(LLMCallLog))` 风格

#### P4: 前端 RAG 查询不支持流式输出
- **位置**: `frontend/src/services/ragService.ts`
- **现象**: `queryKnowledgeBase` 只调用 `/rag/query`（非流式），未实现 `/rag/query/stream`（SSE）
- **影响**: RAG 问答时用户需等待完整响应，体验不如 Chat 的流式输出
- **修复方案**: 添加 `streamQueryKnowledgeBase` 函数，类似 `streamChatMessage` 的 SSE 实现

#### P5: 前端多处 catch 块为空
- **位置**: `KnowledgePage.tsx` L33/L47/L57, `KnowledgePanel.tsx` L33/L50/L59/L69
- **现象**: `catch {}` 空块，错误被静默吞掉
- **影响**: 上传失败、查询失败时用户无任何反馈
- **修复方案**: 添加 `toast` 或 `setError` 提示

#### P6: Settings 页面清除 LLM 配置使用空格字符串
- **位置**: `frontend/src/pages/SettingsPage.tsx` L65-69
- **现象**: 清除配置时传 `' '`（空格字符串），后端 `UserService.update_llm_config` 会 strip 后判断空字符串再清除，但传空格字符串作为清除信号不够直观
- **影响**: 逻辑虽然能工作，但代码可读性差，且如果后端逻辑变更可能出问题
- **修复方案**: 后端增加一个 `DELETE /me/llm-config` 端点，或前端传空字符串 `''`

#### P7: Chat 流式模式下 Tool Calling 不可用
- **位置**: `app/services/llm_service.py` → `generate_chat_reply_stream()`
- **现象**: 流式路径不支持 Tool Calling，前端默认使用流式，导致工具调用功能实际上无法触发
- **影响**: 用户在正常使用中无法体验 Tool Calling（创建任务、天气查询等）
- **修复方案**: 实现流式 + Tool Calling 结合，或前端先非流式判断是否需要工具调用，再决定流式/非流式

#### P8: 前端 User 类型缺少字段
- **位置**: `frontend/src/types/index.ts`
- **现象**: `User` 接口只有 `id/username/email/has_custom_llm_key`，缺少 `full_name/is_active/is_superuser/llm_provider/llm_base_url/llm_model_name`
- **影响**: Settings 页面无法回显当前 LLM 配置（provider/base_url/model_name），用户不知道自己配置了什么
- **修复方案**: 扩展 `User` 类型，Settings 页面从 `user` 对象读取当前配置

### 🟢 轻微问题（不影响功能）

#### P9: 前端 KnowledgePage 和 KnowledgePanel 代码重复
- **位置**: `frontend/src/pages/KnowledgePage.tsx` 和 `frontend/src/components/knowledge/KnowledgePanel.tsx`
- **现象**: 两个文件有大量重复的状态标签/颜色映射和文档列表逻辑
- **影响**: 维护成本增加
- **修复方案**: 提取公共常量和组件

#### P10: 前端 API 服务中 chatService 的 stream 使用 fetch 而非 axios
- **位置**: `frontend/src/services/chatService.ts` L31
- **现象**: 流式请求直接用 `fetch`，绕过了 `api.ts` 中的拦截器（如 401 自动跳转登录）
- **影响**: 流式请求 401 时不会自动跳转登录页
- **修复方案**: 在 fetch 请求中也手动处理 401 逻辑，或使用 axios 的 onDownloadProgress

#### P11: 前端 AuthContext 中 JSON.parse 无 try-catch
- **位置**: `frontend/src/contexts/AuthContext.tsx` L18
- **现象**: `JSON.parse(stored)` 如果 localStorage 中的数据被篡改会抛出异常
- **影响**: 极端情况下应用白屏
- **修复方案**: 添加 try-catch，解析失败时清除 localStorage

#### P12: Worker 路由使用 HTTPException 而非 AppException
- **位置**: `app/api/routers/worker.py` L41/L73
- **现象**: 使用 `HTTPException` 而非项目统一的 `AppException`
- **影响**: 错误响应格式不一致（`detail` vs `code/msg/data`）
- **修复方案**: 替换为 `AppException`

#### P13: 健康检查路由路径不一致
- **位置**: `app/api/routers/health.py`
- **现象**: 路由定义了 `prefix="/health"`，在 main.py 中又加了 `prefix="/api/v1"`，但实际访问时 `/api/v1/health/`（带尾部斜杠）返回 404，`/api/v1/health`（不带）返回 200
- **影响**: 可能导致前端或监控工具请求失败
- **修复方案**: 统一尾部斜杠处理

---

## 三、功能增强建议（按优先级排序）

### 🔴 第一优先：核心体验修复

| 序号 | 改进项 | 说明 | 预期收益 |
|------|--------|------|----------|
| F1 | **修复 Setup 首用户 superuser 问题** | P1 修复 | 管理员功能可用 |
| F2 | **前端构建集成到 Docker** | P2 修复 | Docker 部署后前端可用 |
| F3 | **Chat 流式 + Tool Calling 结合** | P7 修复 | 用户能实际体验 Agent 工具调用 |
| F4 | **前端 User 类型扩展 + Settings 回显** | P8 修复 | 用户能看到当前 LLM 配置 |

### 🟡 第二优先：体验提升

| 序号 | 改进项 | 说明 | 预期收益 |
|------|--------|------|----------|
| F5 | **RAG 查询流式输出（前端）** | P4 修复 | RAG 问答体验提升 |
| F6 | **前端错误提示完善** | P5 修复 | 操作失败有反馈 |
| F7 | **增加 2-3 个更有说服力的工具** | 如邮件发送、GitHub Issue 创建、Slack 通知 | 展示真实 Agent 能力 |
| F8 | **RAG 提问建议功能** | 上传文档后自动生成可提问建议 | 降低用户使用门槛 |
| F9 | **对话历史持久化** | 当前刷新页面后对话丢失 | 支持多轮上下文 |
| F10 | **文档上传进度指示** | 大文件上传时显示进度条 | 用户体验提升 |

### 🟢 第三优先：工程完善

| 序号 | 改进项 | 说明 | 预期收益 |
|------|--------|------|----------|
| F11 | **统一 SQLAlchemy 查询语法** | P3 修复 | 代码一致性 |
| F12 | **统一异常处理（AppException）** | P12 修复 | 响应格式一致 |
| F13 | **前端代码去重** | P9 修复 | 可维护性 |
| F14 | **增加 pgvector HNSW 索引** | 大规模检索性能 | 面试加分 |
| F15 | **使用异步 SQLAlchemy** | 当前同步引擎 | 性能 + 面试加分 |
| F16 | **更多接口限流保护** | 当前仅 Chat 有限流 | 安全性 |
| F17 | **更多文档格式支持 (.docx/.html)** | 在 file_parser 基础上扩展 | 功能覆盖 |
| F18 | **用户邮箱验证流程** | 注册即激活 | 用户体系完善 |
| F19 | **部署到线上** | Railway/Render/阿里云 | 面试官直接体验 |
| F20 | **录制操作 Demo GIF** | README 首屏展示 | 最直观的展示 |

---

## 四、原有 PROJECT_REVIEW.md 改进建议对照

以下为原 PROJECT_REVIEW.md 中的改进建议，标注当前状态：

| 原序号 | 改进项 | 原优先级 | 当前状态 | 备注 |
|--------|--------|----------|----------|------|
| 1 | 部署到线上 | 🔴 | ⬜ 未完成 | → F19 |
| 2 | 录制 Demo GIF | 🔴 | ⬜ 未完成 | → F20 |
| 3 | 精美化 Demo 页面 | 🔴 | ✅ 已完成 | React SPA 已构建 |
| 4 | 准备讲解视频 | 🔴 | ⬜ 未完成 | 非代码层面 |
| 5 | 增加 2-3 个工具 | 🟡 | ⬜ 未完成 | → F7 |
| 6 | Chat 工具调用支持流式 | 🟡 | ⬜ 未完成 | → F3 |
| 7 | RAG 提问建议 | 🟡 | ⬜ 未完成 | → F8 |
| 8 | pgvector HNSW 索引 | 🟡 | ⬜ 未完成 | → F14 |
| 9 | 压力测试报告 | 🟡 | ⬜ 未完成 | — |
| 10 | 更多接口限流 | 🟢 | ⬜ 未完成 | → F16 |
| 11 | 异步 SQLAlchemy | 🟢 | ⬜ 未完成 | → F15 |
| 12 | 更多文档格式 | 🟢 | ⬜ 未完成 | → F17 |
| 13 | 用户邮箱验证 | 🟢 | ⬜ 未完成 | → F18 |
| 14 | 统一查询语法 | 🟢 | ⬜ 未完成 | → F11 |

### 本次测试新发现的问题（原 REVIEW 未覆盖）

| 编号 | 问题 | 优先级 |
|------|------|--------|
| P1 | Setup 首用户非 superuser | 🔴 |
| P2 | 前端未构建到 Docker 镜像 | 🔴 |
| P4 | 前端 RAG 查询不支持流式 | 🟡 |
| P5 | 前端空 catch 块 | 🟡 |
| P6 | Settings 清除配置用空格字符串 | 🟡 |
| P7 | Chat 流式模式 Tool Calling 不可用 | 🟡 |
| P8 | 前端 User 类型缺少字段 | 🟡 |
| P9 | KnowledgePage/Panel 代码重复 | 🟢 |
| P10 | chatService stream 绕过 axios 拦截器 | 🟢 |
| P11 | AuthContext JSON.parse 无保护 | 🟢 |
| P12 | Worker 路由使用 HTTPException | 🟢 |
| P13 | 健康检查路径尾部斜杠不一致 | 🟢 |

---

## 五、建议执行路线图

### Phase 1：核心修复（1-2 天）
1. 修复 P1: Setup 首用户 superuser 问题
2. 修复 P2: 前端构建集成到 Docker
3. 修复 P8: 前端 User 类型扩展
4. 修复 P12: Worker 路由异常统一

### Phase 2：体验提升（2-3 天）
1. 修复 P7: Chat 流式 + Tool Calling
2. 修复 P4: RAG 查询流式输出
3. 修复 P5: 前端错误提示
4. 修复 P3: 统一 SQLAlchemy 语法
5. 修复 P6: Settings 清除配置方式

### Phase 3：功能增强（3-5 天）
1. F7: 新增 2-3 个工具
2. F9: 对话历史持久化
3. F8: RAG 提问建议
4. F10: 文档上传进度指示

### Phase 4：工程完善（持续）
1. F14: HNSW 索引
2. F15: 异步 SQLAlchemy
3. F16: 更多接口限流
4. F19: 部署到线上
5. F20: 录制 Demo GIF

---

## 六、测试覆盖率统计

| 模块 | API 测试 | 前端测试 | 备注 |
|------|----------|----------|------|
| 认证 (Auth) | 7/7 ✅ | ✅ | Setup/Login/权限 |
| 用户 (Users) | 6/6 ✅ | ✅ | CRUD/BYOK/密码 |
| 任务 (Tasks) | 10/10 ✅ | ✅ | CRUD/隔离/分页 |
| 聊天 (Chat) | 5/7 ⚠️ | ✅ | Mock 模式下 Tool Calling 未实际触发 |
| RAG | 9/9 ✅ | ✅ | 上传/查询/删除 |
| Worker | 3/3 ✅ | — | 任务提交/状态查询 |
| 可观测性 | 3/3 ✅ | ✅ | 日志/统计 |
| 基础设施 | 4/4 ✅ | — | Health/Metrics/Swagger/Rate Limit |
| **总计** | **47/49** | **全部页面** | **通过率 95.9%** |
