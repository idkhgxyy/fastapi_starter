# 简历项目描述

## 版本一：适合一段式直接写进简历（推荐）
基于 `FastAPI + PostgreSQL + Redis + Celery + Ollama` 独立搭建个人知识库与任务执行 Agent 系统，含完整 React SPA 前端。完成 JWT 鉴权、按用户隔离的 RAG 知识库检索问答（多文档格式 + SSE 流式）、Tool Calling 多工具调用与异步文档处理、MCP 协议工具层；使用 `pgvector` 向量检索 + `BGE-Reranker` 重排，接入 `Prometheus + Grafana` 监控并设计 LLM 调用日志体系，支持按用户 / 按天统计 token、耗时、错误与成本，具备全栈工程化交付与可观测能力。

## 版本二：一段式压缩版（适合简历空间有限）
基于 `FastAPI + React + PostgreSQL + Redis + Celery + Ollama` 独立开发全栈 AI Agent 系统，完成 JWT 鉴权、任务管理、按用户隔离的 RAG 检索问答、Tool Calling、MCP 协议工具层与真实异步文档处理；基于 `pgvector` 实现向量检索并兼容 `BGE-Reranker` 二次重排，接入 `Prometheus + Grafana` 监控与 LLM 调用日志体系，支持按用户 / 按天统计 token、耗时、错误与成本，具备较完整的工程化交付与可观测能力。

## 版本三：适合 STAR 风格展开
### 项目名称
全栈 AI Agent 系统 — 个人知识库 + 任务执行 Agent

### 项目职责
- 独立负责后端架构设计、数据库建模、接口实现与前端开发
- 完成 LLM 接入、Tool Calling、MCP 协议工具层、RAG 检索链路、用户隔离设计与异步任务体系
- 搭建 Prometheus / Grafana 监控和 LLM 调用日志统计能力
- 构建 React SPA 前端，覆盖 AI 对话、知识库管理、可观测面板等 8 个页面

### 技术栈
`FastAPI`、`React`、`TypeScript`、`SQLAlchemy`、`PostgreSQL`、`pgvector`、`Redis`、`Celery`、`Ollama`、`MCP`、`Prometheus`、`Grafana`、`Docker Compose`

### 结果亮点
- 设计并实现用户系统与 JWT 鉴权体系，支持登录态访问 AI 能力与业务数据
- 实现任务管理模块，提供创建、分页、过滤、更新、删除等接口，并支持 Agent 直接调用工具创建任务
- 实现 RAG 知识库完整链路：多格式文档上传（.txt/.md/.pdf）、状态管理、异步切分、Embedding、pgvector 检索、BGE-Reranker 重排、SSE 流式问答、多轮对话记忆
- 为知识库增加用户级数据隔离，检索仅作用于当前用户已处理完成的文档
- 本地接入 `qwen2.5:3b` 与 `bge-m3`，实现低成本、离线可运行的 AI 应用方案
- 基于 Celery + Redis 实现长耗时任务处理能力，支撑文档入库、重处理和状态跟踪等异步流程
- 基于 MCP 协议统一管理 5 个工具（天气查询/任务创建/系统状态/任务列表/安全计算器），支持装饰器式注册与统一调度
- 基于 Prometheus + Grafana 构建接口级监控面板，支持请求量、耗时、错误率可视化
- 自建 LLM Observability 模块，记录 prompt、response、tool_calls、tokens、latency、request_id 与 error，支持按天 / 按用户 / 按接口统计
- 构建 React + TypeScript 前端 SPA，SSE 流式渲染、ToolCallCard 可视化、Mock 模式离线开发、深色主题
- 121+ 单元测试覆盖核心模块，CI/CD（GitHub Actions + PostgreSQL 集成测试）

## 版本四：面试时 30 秒口头介绍
我独立完成了一个全栈 AI Agent 项目，不只是接模型聊天，还完整实现了用户体系、任务系统、按用户隔离的 RAG、Tool Calling、MCP 协议工具层、异步处理和监控。前端用 React 做了完整的 SPA，后端模型层使用本地 Ollama，数据层用了 PostgreSQL 和 pgvector 并兼容 reranker 重排；工程上补了 JWT、Celery、Prometheus、Grafana、LLM 调用日志和成本统计，121 个单元测试再加 CI/CD，比较能体现我在全栈工程和 AI 应用落地上的能力。

## 可提炼的关键词
- `全栈开发`
- `Python 后端` / `React 前端`
- `FastAPI`
- `LLM Agent`
- `RAG`
- `Tool Calling`
- `MCP 协议`
- `JWT 鉴权`
- `异步任务`
- `可观测性`
- `Docker Compose`
- `生产级工程化`
