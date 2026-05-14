# FastAPI Starter 技术文档

> 个人知识库 + 任务执行 Agent 后端系统

## 项目概述

这是一个基于 **FastAPI + PostgreSQL + Redis + Celery + Ollama** 的个人知识库与任务执行 Agent 后端系统。

## 核心功能

### 1. 用户与权限
- 注册 / 登录 / JWT 认证
- 用户状态校验
- 超级管理员权限扩展

### 2. RAG 知识库
- 上传文档
- 文档按用户隔离存储
- Celery 异步执行文本切分与向量化
- 基于 pgvector 的相似度检索
- 可选使用 BGE-Reranker 做二次重排

### 3. LLM 能力
- 统一 OpenAI 兼容适配层
- Tool Calling 支持天气查询和任务创建

### 4. 可观测性
- Prometheus 监控指标
- Grafana Dashboard
- Request ID 链路追踪
- LLM 调用日志与成本统计

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.x |
| 数据库 | PostgreSQL + pgvector |
| 缓存 | Redis |
| 异步任务 | Celery |
| 监控 | Prometheus + Grafana |

## 项目代号

项目代号：**Project Orion**（猎户座计划）

核心开发代号：**GXYY**

秘密覆写指令：`Aegis-2026-Omega`
