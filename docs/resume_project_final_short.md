# 简历最终压缩版

基于 `FastAPI + PostgreSQL + Redis + Celery + Ollama` 独立开发个人知识库与任务执行 Agent 后端，完成 `JWT` 鉴权、任务管理、RAG 检索问答、Tool Calling、多步工具调用与异步文档处理；基于 `pgvector` 实现向量检索，接入 `Prometheus + Grafana` 监控，并设计 LLM 调用日志体系，支持按用户 / 按天统计 `token`、耗时、错误与成本，具备较完整的工程化交付与可观测能力。

## 更短一版
独立完成一个基于 `FastAPI` 的 AI Agent 后端系统，支持用户鉴权、任务管理、RAG、Tool Calling、异步任务与本地 Ollama 模型接入，并通过 `Prometheus + Grafana + LLM 日志` 实现接口与模型调用的可观测。

## 面试时 30 秒版本
我做了一个偏生产级的 FastAPI AI 后端项目，不只是接模型聊天，还完整实现了用户体系、任务系统、RAG、Tool Calling、异步处理和监控。模型层使用本地 Ollama，数据层用了 PostgreSQL 和 pgvector，工程上补了 JWT、Celery、Prometheus、Grafana，以及 LLM 调用日志和成本统计，比较能体现我在 Python 后端和 AI 应用工程化落地上的能力。
