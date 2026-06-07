# FastAPI AI Agent — 前端 SPA

FastAPI Starter 项目的现代化前端，覆盖 AI 对话、RAG 知识库、任务管理、可观测性面板等全部后端能力。

## 技术栈

- **React 19** + **TypeScript**（strict 模式）
- **Vite 8** 构建工具，HMR 热更新
- **Tailwind CSS v4** + `@tailwindcss/typography`
- **React Router v7** 客户端路由
- **Recharts** 可观测性图表
- **Axios** HTTP 客户端（含 Mock 拦截器）
- **react-markdown** + **remark-gfm** Markdown 渲染

## 快速开始

### 方式一：连接后端运行（推荐）

```bash
# 1. 确保后端已启动（详见项目根目录 README）
# 2. 安装前端依赖
cd frontend && npm install

# 3. 启动开发服务器，自动代理 API 到后端
npm run dev
```

访问 `http://localhost:5173`

### 方式二：Mock 模式（离线开发，无需后端）

```bash
cd frontend && npx vite --host --mode mock
```

所有 API 调用将返回本地 Mock 数据，可完全离线开发调试。

### 方式三：生产构建

```bash
cd frontend && npm run build
```

构建产物在 `dist/` 目录，可直接部署到静态托管服务（Vercel / Railway / Nginx）。

## 项目结构

```
frontend/
├── src/
│   ├── components/           # UI 组件
│   │   ├── auth/             # 认证相关（ProtectedRoute）
│   │   ├── chat/             # 对话（ChatArea, ChatInput, MessageList, ToolCallCard）
│   │   ├── knowledge/        # 知识库（KnowledgePanel）
│   │   ├── layout/           # 布局（Navbar, Sidebar, ChatLayout）
│   │   ├── observability/    # 可观测性（StatsCards, TrendChart, EndpointChart, LLMCallLogTable）
│   │   ├── tasks/            # 任务（TasksPanel, TaskStatusBadge）
│   │   └── ui/               # 通用（ErrorBoundary, Icons）
│   ├── contexts/             # React Context（AuthContext, ThemeContext）
│   ├── hooks/                # 自定义 Hook（useChat SSE 流式对话）
│   ├── mock/                 # Mock 数据层（全 API 覆盖）
│   ├── pages/                # 8 个路由页面
│   ├── services/             # 7 个 API Service 模块
│   └── types/                # TypeScript 类型定义
├── .env.mock                 # Mock 模式环境变量
├── index.html
├── package.json
├── vite.config.ts            # Vite 配置（含 API 代理）
└── tsconfig.json             # TypeScript 配置（strict 模式）
```

## 路由与页面

| 路径 | 页面 | 认证 | 说明 |
|------|------|------|------|
| `/chat` | 聊天主页 | 是 | AI 对话 + 侧边栏（知识库/任务） |
| `/auth/login` | 登录 | 否 | 邮箱密码登录 / Token 粘贴 |
| `/auth/register` | 注册 | 否 | 注册后自动登录 |
| `/knowledge` | 知识库管理 | 是 | 上传文档、查看状态、RAG 搜索 |
| `/tasks` | 任务管理 | 是 | 创建/过滤/切换状态/删除任务 |
| `/observability` | 可观测性面板 | 是 | LLM 统计卡片、趋势图、日志列表 |
| `/settings` | 用户设置 | 是 | LLM 配置（多厂商 BYOK）、修改密码 |
| `/health` | 系统健康 | 否 | DB/Redis/Ollama 三服务状态灯 |

## 架构设计

```
用户操作 → Page 页面
            ├── Context（全局状态：Auth / Theme）
            ├── Service（API 请求封装，含 Token 自动注入）
            ├── Hook（useChat 管理 SSE 流式连接状态）
            └── Component（纯 UI 展示）
```

- **Service 层**：每个后端模块对应一个 Service（authService / chatService / ragService 等），统一管理 API 调用和 Mock 切换
- **Context 层**：AuthContext 管理登录态，ThemeContext 管理深色/浅色主题
- **Hook 层**：`useChat` 封装 SSE 流式连接的建立、数据接收、错误处理和自动重连
- **Mock 层**：通过 `VITE_USE_MOCK` 环境变量切换，Axios 拦截器注入 Mock 数据

## 可观测性面板

可观测性是本项目的差异化亮点，包含：

- **统计卡片**：总调用次数、Token 消耗、总耗时、估算成本
- **趋势折线图**：近 7/14/30 天的 LLM 调用趋势
- **端点柱状图**：按 API 端点的调用量分布
- **调用日志表格**：支持分页查看，点击展开详情 Modal（展示 prompt / response / tool_calls）

## 浏览器支持

- Chrome / Edge（最新 2 个版本）
- Firefox（最新 2 个版本）
- Safari 15+
- 移动端浏览器（响应式布局）

## 开发规范

- TypeScript strict 模式，禁止 `any`
- 函数式组件 + Hooks
- Tailwind CSS 原子类
- 组件文件不超过 200 行
