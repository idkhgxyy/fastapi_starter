# FastAPI AI Agent — 前端应用需求文档 (PRD)

> **⚠️ 历史文档**：此文档是前端开发启动前的 PRD（产品需求文档/规格说明）。最终实现版本已落地为 `frontend/` 目录下的完整 React SPA，详细说明请见 [frontend/README.md](../frontend/README.md)。此文档保留作为项目规划能力的参考。
>
> 版本：v1.0
> 目标读者：前端开发者 / 面试官
> 定位：一份可直接作为前端开发规范的 PRD，展示了后端项目的完整前端配套需求

---

## 1. 项目背景与定位

### 1.1 一句话描述

> 为一个生产级 FastAPI AI Agent 后端构建现代化前端界面，提供知识库问答、任务管理、AI 对话、可观测性面板等核心功能。

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| **完整覆盖后端能力** | 对接全部 25 个 API 端点，无功能遗漏 |
| **面试级质量** | 代码规范、组件复用、状态管理清晰，能体现前端工程能力 |
| **响应式 + 深色模式** | 桌面/移动端适配，跟随系统主题 |
| **开箱即用** | 提供 Mock 模式，无需后端也能独立开发调试 |

---

## 2. 技术栈建议

| 层次 | 技术选型 | 理由 |
|------|----------|------|
| 框架 | **React 18+** / **Vue 3** (二选一) | 生态成熟，校招主流 |
| 构建工具 | **Vite** | 冷启动快，HMR 高效 |
| 路由 | React Router v6 / Vue Router 4 | 多页面管理 |
| 状态管理 | React Context / Pinia | 轻量，够用 |
| UI 组件 | **Tailwind CSS** + headless-ui | 与现有 demo.html 风格统一 |
| HTTP 客户端 | **axios** / fetch | 拦截器处理 Token 注入 |
| 流式响应 | **EventSource** / fetch + ReadableStream | SSE 协议对接 |
| Markdown 渲染 | **react-markdown** / marked | AI 回复渲染 |
| 图表库 | **Recharts** / Chart.js | 可观测性面板 |

---

## 3. 页面架构

```
/                               # 根，重定向到 /chat
├── /auth/login                 # 登录页
├── /auth/register              # 注册页
├── /chat                       # 主聊天页（核心）
│   ├── 左侧：知识库面板
│   ├── 左侧：任务面板
│   ├── 中间：聊天会话
│   └── 底部：输入区
├── /tasks                      # 任务管理页（独立视图）
├── /knowledge                  # 知识库管理页（独立视图）
├── /observability              # 可观测性面板
│   ├── LLM 调用日志
│   ├── Token 用量统计
│   └── API 健康状态
├── /settings                   # 用户设置
│   ├── LLM 配置
│   └── 修改密码
└── /health                     # 系统健康状态页
```

---

## 4. 页面详细需求

### 4.1 登录 / 注册页 (`/auth/login`, `/auth/register`)

**功能描述**：用户认证入口。

**UI 结构**：
- 居中卡片布局，简洁美观
- 两个 Tab 切换：登录 / 注册
- 登录表单：邮箱 + 密码
- 注册表单：用户名 + 邮箱 + 密码
- "粘贴 Token 直接登录" 折叠面板（高级用户入口）

**交互流程**：

```
[登录 Tab]
  输入邮箱 + 密码
  POST /api/v1/auth/login  (x-www-form-urlencoded)
  → 成功：Token 存 localStorage，跳转 /chat
  → 失败：显示错误提示

[注册 Tab]
  输入用户名 + 邮箱 + 密码
  POST /api/v1/users/
  → 成功：自动用刚注册的账号调用登录接口
  → 失败：显示错误提示

[Token 登录]
  粘贴 JWT Token
  存入 localStorage，跳转 /chat
```

**API 依赖**：
- `POST /api/v1/auth/login`
- `POST /api/v1/users/`

**错误处理**：
- 网络错误 → "连接服务器失败，请检查网络"
- 401 → "邮箱或密码错误"
- 重复注册 → "该邮箱已被注册"

---

### 4.2 聊天主页 (`/chat`)

**功能描述**：AI 对话主界面，集成知识库搜索和任务管理侧边栏。这是整个应用的核心页面（当前 demo.html 的升级版）。

**UI 结构**：

```
┌─────────────────────────────────────────────────────┐
│  Navbar: Logo | 搜索 | 通知 | 用户头像▼ | 深色模式  │
├──────────────┬──────────────────────────────────────┤
│ Sidebar(320px)│  Chat Area                          │
│ ┌─ Tabs ────┐ │  ┌─ 消息列表 ──────────────────────┐│
│ │ 知识库 | 任务││  │ (User) 你好，帮我查一下今天的天气 ││
│ ├────────────┤ │  │ (AI)   好的，正在查询...        ││
│ │ [知识库面板]  │ │  │ (Tool) 调用 get_current_weather││
│ │  ·上传区域   │ │  │ (AI)   北京今天晴天 25°C...   ││
│ │  ·搜索输入框 │ │  └───────────────────────────────┘│
│ │  ·文档列表   │ │  ┌─ 输入区 ──────────────────────┐│
│ ├────────────┤ │  │ [聊天输入框...]  [发送]         ││
│ │ [任务面板]   │ │  └───────────────────────────────┘│
│ │  ·创建表单   │ │                                    │
│ │  ·任务列表   │ │                                    │
│ └────────────┘ │                                    │
└──────────────┴──────────────────────────────────────┘
```

**交互流程**：

```
→ 页面加载时自动获取用户信息
  GET /api/v1/users/me
  → 展示用户名

→ 用户输入消息，按 Enter 发送
  POST /api/v1/chat/  { message, stream: true }
  → SSE 流式渲染 AI 回复
  → 支持展示 Tool Calling 中间过程（折叠显示）

→ 输入框自动调整高度 (max-h-32)
  Shift+Enter 换行

→ 会话历史：浏览器本地存储最近 10 条对话
```

**SSE 流式渲染规范**：

```typescript
// 后端流式响应格式
interface SSEChunk {
  reasoning?: string;    // 思考过程（如有）
  content?: string;      // 回复内容片段
}

// 处理逻辑
const eventSource = new EventSource(url);
eventSource.onmessage = (event) => {
  if (event.data === "[DONE]") {
    eventSource.close();
    return;
  }
  const chunk = JSON.parse(event.data);
  if (chunk.reasoning) {
    // 以黄色背景框渲染思考过程
  }
  if (chunk.content) {
    // 追加到当前 AI 消息气泡
  }
};
```

**Tool Calling 可视化**：当 AI 调用工具时，在聊天中以"系统卡片"形式展示：
```
┌─ 🔧 调用工具 ─────────────────┐
│  工具: get_current_weather     │
│  参数: { "location": "北京" }  │
│  结果: "北京今天晴天 25°C"     │
└────────────────────────────────┘
```

**API 依赖**：
- `POST /api/v1/chat/`（核心）
- `GET /api/v1/users/me`（获取用户名）
- `GET /api/v1/rag/documents`（侧边栏文档列表）
- `POST /api/v1/rag/upload`（上传文档）
- `POST /api/v1/rag/query/stream`（RAG 流式查询）
- `GET /api/v1/tasks/`（侧边栏任务列表）
- `POST /api/v1/tasks/`（创建任务）
- `PUT /api/v1/tasks/{id}`（更新任务状态）
- `DELETE /api/v1/tasks/{id}`（删除任务）

---

### 4.3 知识库管理页 (`/knowledge`)

**功能描述**：知识库文档的独立管理视图，提供比侧边栏更丰富的操作。

**UI 结构**：
- 顶部：拖拽上传区域（支持 .txt / .md / .pdf）
- 中间：文档列表（表格/卡片视图切换）
  - 每项：文件名 + 文件类型 + Chunk 数 + 状态徽章 + 上传时间
  - 状态徽章颜色：queued=灰色, processing=蓝色, ready=绿色, failed=红色
  - 操作：刷新状态、删除文档、重新处理
- 底部：分页/加载更多

**API 依赖**：
- `GET /api/v1/rag/documents`
- `POST /api/v1/rag/upload`
- `GET /api/v1/rag/documents/{id}`
- `POST /api/v1/worker/process`（重新异步处理）
- `GET /api/v1/worker/status/{task_id}`（跟踪处理进度）

---

### 4.4 任务管理页 (`/tasks`)

**功能描述**：任务的独立管理视图。

**UI 结构**：
- 顶部：创建任务表单（标题 + 描述 + 提交）
- 中部：过滤栏（全部 / 待办 / 进行中 / 已完成）
- 主区域：任务卡片列表
  - 每项：标题 + 描述（截断）+ 状态标签 + 创建时间
  - 操作：编辑标题、切换状态、删除
- 空状态："还没有任务，试试让 AI 帮你创建一个"

**API 依赖**：
- `GET /api/v1/tasks/`（支持 skip/limit 分页）
- `POST /api/v1/tasks/`
- `PUT /api/v1/tasks/{id}`
- `DELETE /api/v1/tasks/{id}`

---

### 4.5 可观测性面板 (`/observability`)

**功能描述**：展示 LLM 调用统计和系统健康状态。这是项目的**差异化亮点**。

**UI 结构**：

```
┌─────────────────────────────────────────────────┐
│ [LLM 调用概览]                                   │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│ │ 总调用│ │总Token│ │总耗时 │ │总成本 │           │
│ │  1,234│ │45,678│ │ 12.3s│ │$0.05 │           │
│ └──────┘ └──────┘ └──────┘ └──────┘           │
│                                                 │
│ [近 7 天调用趋势 - 折线图]                        │
│  📈 调用次数 / Token 量 / 成本 随时间变化          │
│                                                 │
│ [LLM 调用日志列表]                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ # | 时间 | 用户 | 端点 | Token | 耗时 | 状态 │ │
│ │ 1 | 14:30 | user1 | /chat | 156 | 2.1s | ✅ │ │
│ │ 2 | 14:29 | user1 | /rag  | 89  | 1.5s | ✅ │ │
│ │ ...                                        │ │
│ └─────────────────────────────────────────────┘ │
│ 点击展开详情 Modal: prompt / response / tool_calls │
└─────────────────────────────────────────────────┘
```

**展示维度**：

| 维度 | 展示形式 | 数据来源 |
|------|----------|----------|
| 总调用次数 | 数字卡片 | GET /api/v1/observability/llm-stats |
| 总 Token 消耗 | 数字卡片 | GET /api/v1/observability/llm-stats |
| 总耗时 | 数字卡片 | GET /api/v1/observability/llm-stats |
| 总成本 | 数字卡片 | GET /api/v1/observability/llm-stats |
| 调用趋势 | 折线图（近 7/14/30 天） | GET /api/v1/observability/llm-stats |
| 日志列表 | 表格 + 分页 | GET /api/v1/observability/llm-calls |
| 日志详情 | Modal | 展开单条记录 |

**API 依赖**：
- `GET /api/v1/observability/llm-stats`（支持 `days` 参数）
- `GET /api/v1/observability/llm-calls`

---

### 4.6 用户设置页 (`/settings`)

**功能描述**：个人 LLM 配置和密码修改。

**UI 结构**：
- **LLM 配置区块**：
  - 服务商（Provider）→ 下拉选择：deepseek / openai / ollama / custom
  - Base URL → 文本输入
  - 模型名称 → 文本输入
  - API Key → 密码输入框（掩码显示，区分"已配置"和"未配置"状态）
  - 保存按钮
- **修改密码区块**：
  - 旧密码 + 新密码 + 确认新密码
  - 保存按钮
- **提示信息**："配置个人 LLM Key 后，系统将优先使用你的配置，不再使用全局 Key"

**API 依赖**：
- `GET /api/v1/users/me`（加载当前配置）
- `PUT /api/v1/users/me/llm-config`
- `PUT /api/v1/users/me/password`

---

### 4.7 系统健康页 (`/health`)

**功能描述**：展示系统各依赖服务的运行状态。

**UI 结构**：
- 三个状态卡片：Database / Redis / Ollama
- 每个卡片：名称 + 状态指示灯（绿/黄/红）+ 延迟时间 + 错误详情
- 整体状态摘要："所有服务正常" / "部分服务异常"
- 自动刷新按钮 / 10 秒自动轮询

**API 依赖**：
- `GET /api/v1/health`

---

## 5. 全局设计规范

### 5.1 主题

- 支持 **浅色/深色** 双主题，跟随系统 `prefers-color-scheme`
- 手动切换按钮在 Navbar 上
- CSS 变量驱动，所有颜色通过 `--color-*` 变量定义

### 5.2 响应式断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| 移动端 | < 768px | 隐藏侧边栏，底部 Tab 切换 |
| 平板 | 768px ~ 1024px | 侧边栏可折叠 |
| 桌面 | > 1024px | 完整三栏布局 |

### 5.3 全局状态管理

```typescript
interface AppState {
  auth: {
    token: string | null;
    user: User | null;
    isAuthenticated: boolean;
  };
  ui: {
    theme: "light" | "dark";
    sidebarOpen: boolean;
    sidebarTab: "knowledge" | "tasks";
  };
  chat: {
    messages: Message[];
    isStreaming: boolean;
  };
}
```

### 5.4 HTTP 请求规范

```typescript
// axios 拦截器配置
const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("agent_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("agent_token");
      window.location.href = "/auth/login";
    }
    return Promise.reject(error);
  }
);
```

### 5.5 错误与加载状态

| 状态 | 展示方式 |
|------|----------|
| Loading | Skeleton 骨架屏 / spinner |
| 空数据 | 插画 + 引导文字 + 操作按钮 |
| 错误 | Toast 通知 + 重试按钮 |
| 全局错误 | 错误 Boundary 组件 |

---

## 6. 路由设计

| 路径 | 页面 | 认证 | 备注 |
|------|------|------|------|
| `/` | 重定向到 `/chat` | - | - |
| `/auth/login` | 登录 | 否 | 已登录则跳转 /chat |
| `/auth/register` | 注册 | 否 | 注册成功自动登录 |
| `/chat` | 聊天主页（核心） | 是 | - |
| `/knowledge` | 知识库管理 | 是 | - |
| `/tasks` | 任务管理 | 是 | - |
| `/observability` | 可观测性面板 | 是 | - |
| `/settings` | 用户设置 | 是 | LLM 配置 + 密码 |
| `/health` | 系统健康状态 | 否 | 公开页面 |

路由守卫：未认证用户访问需要登录的页面时，重定向到 `/auth/login`。

---

## 7. 组件树设计

```
App
├── ThemeProvider（主题上下文）
├── AuthProvider（认证上下文）
├── Router
│   ├── PublicRoute
│   │   ├── LoginPage
│   │   ├── RegisterPage
│   │   └── HealthPage
│   └── ProtectedRoute
│       ├── ChatLayout
│       │   ├── Navbar
│       │   │   ├── Logo
│       │   │   ├── SearchBar
│       │   │   ├── ThemeToggle
│       │   │   └── UserMenu (头像 + 下拉)
│       │   ├── Sidebar
│       │   │   ├── TabBar (知识库 | 任务)
│       │   │   ├── KnowledgePanel
│       │   │   │   ├── FileUploadZone
│       │   │   │   ├── RAGQuery (输入 + TopK滑块)
│       │   │   │   └── DocumentList
│       │   │   │       └── DocumentItem
│       │   │   └── TasksPanel
│       │   │       ├── TaskCreateForm
│       │   │       └── TaskList
│       │   │           └── TaskCard
│       │   ├── ChatArea
│       │   │   ├── MessageList
│       │   │   │   ├── UserMessage (右对齐气泡)
│       │   │   │   ├── AIMessage (左对齐气泡 + Markdown)
│       │   │   │   ├── ToolCallCard (工具调用卡片)
│       │   │   │   └── TypingIndicator
│       │   │   └── ChatInput
│       │   └── LLMConfigModal
│       ├── KnowledgePage (独立视图)
│       ├── TasksPage (独立视图)
│       ├── ObservabilityPage
│       │   ├── StatsCards
│       │   ├── TrendChart
│       │   └── LLMCallLogTable
│       │       └── LLMCallDetailModal
│       └── SettingsPage
│           ├── LLMConfigForm
│           └── PasswordChangeForm
```

---

## 8. Mock 模式（离线开发）

为了不依赖后端也能开发，必须提供 Mock 数据层：

```typescript
// src/mock/index.ts
// 通过环境变量 VITE_USE_MOCK=true 切换

const MOCK_RESPONSES = {
  "POST /api/v1/auth/login": {
    access_token: "mock-jwt-token",
    token_type: "bearer",
  },
  "GET /api/v1/users/me": {
    id: 1,
    username: "DemoUser",
    email: "demo@example.com",
    has_custom_llm_key: false,
  },
  "POST /api/v1/chat/": {
    reply: "这是 Mock 模式下的回复，用于前端独立开发调试。",
  },
  // ... 更多 Mock 数据
};
```

---

## 9. 开发规范

### 9.1 Git 分支策略

```
main         ← 稳定版本
├── dev      ← 开发主线
├── feat/ui  ← UI 组件开发
├── feat/api ← API 对接
└── fix/*    ← Bug 修复
```

### 9.2 编码规范

- TypeScript 严格模式，禁止 `any`
- 组件使用函数式组件 + Hooks
- CSS 使用 Tailwind 原子类，自定义样式使用 CSS Modules
- 每个组件不超过 200 行
- 页面组件放在 `pages/`，业务组件放在 `components/`，通用组件放在 `shared/`

### 9.3 测试要求

| 测试类型 | 覆盖率目标 | 工具 |
|----------|-----------|------|
| 组件单元测试 | 核心组件 80%+ | Vitest + Testing Library |
| 页面集成测试 | 每个页面一个 | Playwright |
| E2E 测试 | 核心流程覆盖 | Playwright |

---

## 10. 验收标准

| 编号 | 验收项 | 验证方式 |
|------|--------|----------|
| A1 | 用户可注册、登录、退出 | E2E 测试 |
| A2 | 登录后 Token 持久化，刷新不丢失 | 手动验证 |
| A3 | Token 过期后自动跳转登录页 | 手动验证 |
| B1 | 可发送聊天消息，流式渲染回复 | E2E 测试 |
| B2 | AI 回复中的 Markdown 正常渲染 | 手动验证 |
| B3 | Tool Calling 中间步骤以卡片形式展示 | 手动验证 |
| C1 | 可上传文档，状态实时更新 | E2E 测试 |
| C2 | 可进行 RAG 知识库搜索，结果带引用 | 手动验证 |
| D1 | 可创建/查看/更新/删除任务 | E2E 测试 |
| E1 | 可观测性页面展示统计图表 | 手动验证 |
| E2 | LLM 调用日志列表可正常分页查看 | 手动验证 |
| F1 | 响应式布局，移动端可正常使用 | 手动验证 |
| F2 | 深色模式切换正常 | 手动验证 |

---

## 11. 面试话术

当面试官问到这个前端项目时，可以这样介绍：

> **"我在后端项目的基础上，构建了一个完整配套的现代化前端应用。采用了 React + TypeScript + Tailwind CSS 技术栈，覆盖了 AI 对话、RAG 知识库、任务管理、可观测性面板等核心场景。设计上重点做了几个事情：一是 SSE 流式渲染，实现了 AI 回复的打字机效果并保留了 Tool Calling 的中间过程可视化；二是全局认证状态管理，Token 自动注入、过期自动跳转；三是为可观测性面板提供了图标化的 LLM 调用统计，让用户能直观看到 Token 消耗和成本。整个项目有完整的 Mock 层，可以不依赖后端独立开发。"**

---

## 12. 附录：API 参考汇总

| 方法 | 路径 | 请求 | 响应 | 备注 |
|------|------|------|------|------|
| POST | /api/v1/auth/login | FormData { username(email), password } | { access_token, token_type } | OAuth2 兼容 |
| POST | /api/v1/users/ | { username, email, password } | User 对象 | - |
| GET | /api/v1/users/me | - | User 对象 | 需要登录 |
| PUT | /api/v1/users/me/llm-config | { provider?, base_url?, model_name?, api_key? } | User 对象 | - |
| PUT | /api/v1/users/me/password | { current_password, new_password } | { message } | - |
| POST | /api/v1/chat/ | { message, stream } | ChatResponse / SSE | 流式/非流式 |
| GET | /api/v1/tasks/ | ?skip=0&limit=10 | Task[] | - |
| POST | /api/v1/tasks/ | { title, description? } | Task | - |
| PUT | /api/v1/tasks/{id} | { title?, description?, status? } | Task | - |
| DELETE | /api/v1/tasks/{id} | - | { message } | - |
| POST | /api/v1/rag/upload | FormData { file } | Document | 自动提交异步处理 |
| GET | /api/v1/rag/documents | - | Document[] | - |
| GET | /api/v1/rag/documents/{id} | - | Document | 文档详情与处理状态 |
| DELETE | /api/v1/rag/documents/{id} | - | { message } | 删除文档及向量块 |
| POST | /api/v1/rag/query | { query, top_k?, session_id? } | { answer, source_chunks } | 支持多轮对话 (session_id) |
| POST | /api/v1/rag/query/stream | { query, top_k?, session_id? } | SSE | 流式 RAG + 多轮对话 |
| POST | /api/v1/worker/process | { document_id } | { task_id, status } | 重新异步处理文档 |
| GET | /api/v1/worker/status/{task_id} | - | { task_id, status, result? } | 跟踪异步任务进度 |
| GET | /api/v1/observability/llm-stats | ?days=7 | Stats 对象 | 含 daily/endpoint/user 维度 |
| GET | /api/v1/observability/llm-calls | ?skip=0&limit=20 | LLMCallLog[] | 支持分页，含 prompt/response/tool_calls |
| GET | /api/v1/health | - | HealthStatus | 公开 |
