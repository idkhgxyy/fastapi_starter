# 简历项目描述

## 版本一：适合一段式直接写进简历
基于 `FastAPI + PostgreSQL + Redis + Celery + Ollama` 独立搭建个人知识库与任务执行 Agent 后端系统，完成用户注册登录、JWT 鉴权、任务管理、按用户隔离的 RAG 知识库检索问答、Tool Calling 多工具调用与真实异步文档处理；使用 `pgvector` 实现向量检索，并兼容 `BGE-Reranker` 二次重排，接入 `Prometheus + Grafana` 监控，并设计 LLM 调用日志体系，支持按用户 / 按天统计 token、耗时、错误与成本，具备较完整的工程化交付与可观测能力。

## 版本二：适合 STAR 风格展开
### 项目名称
个人知识库 + 任务执行 Agent

### 项目职责
- 独立负责后端架构设计、数据库建模、接口实现与部署调试
- 完成 LLM 接入、Tool Calling、RAG 检索链路、用户隔离设计与异步任务体系
- 搭建 Prometheus / Grafana 监控和 LLM 调用日志统计能力

### 技术栈
`FastAPI`、`SQLAlchemy`、`PostgreSQL`、`pgvector`、`Redis`、`Celery`、`Ollama`、`Prometheus`、`Grafana`、`Docker Compose`

### 结果亮点
- 设计并实现用户系统与 JWT 鉴权体系，支持登录态访问 AI 能力与业务数据
- 实现任务管理模块，提供创建、分页、过滤、更新、删除等接口，并支持 Agent 直接调用工具创建任务
- 实现 RAG 知识库链路：文档上传、状态查询、异步切分、Embedding、向量检索、带引用回答
- 为知识库增加用户级数据隔离，检索仅作用于当前用户已处理完成的文档
- 兼容 `BGE-Reranker` 二次重排能力，提升召回结果排序质量
- 本地接入 `qwen2.5:3b` 与 `bge-m3`，实现低成本、离线可运行的 AI 应用方案
- 基于 `Celery + Redis` 实现长耗时任务处理能力，支撑文档入库、重处理和状态跟踪等异步流程
- 基于 `Prometheus + Grafana` 构建接口级监控面板，支持请求量、耗时、错误率可视化
- 自建 LLM Observability 模块，记录 prompt、response、tool_calls、tokens、latency、request_id 与 error，支持按天 / 按用户 / 按接口统计
- 补充自动化测试覆盖认证、用户、健康检查以及 RAG 上传 / 查询 / 重处理链路

## 版本三：适合面试时口头介绍
我做了一个偏生产级的 FastAPI AI 后端项目，不是简单接个模型聊天，而是完整做了用户体系、数据库建模、异步任务、RAG 和工具调用。模型层用的是本地 Ollama，支持 qwen2.5 和 bge-m3；知识库部分做了按用户隔离、pgvector 检索和可选 reranker 重排；工程上补了 JWT、Celery、Prometheus、Grafana，以及 LLM 调用日志和成本统计。这个项目比较能体现我既会 Python 后端，也会做 AI 应用的工程落地。

## 可提炼的关键词
- `Python 后端`
- `FastAPI`
- `LLM Agent`
- `RAG`
- `Tool Calling`
- `JWT 鉴权`
- `异步任务`
- `可观测性`
- `Docker Compose`
- `生产级工程化`
