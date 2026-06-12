.PHONY: help setup up down restart logs seed test shell ollama-pull clean

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## 首次安装：初始化 .env + 启动服务 + 拉模型 + 灌数据
	@bash scripts/bootstrap_local.sh

up: ## 启动核心服务（API + DB + Redis + Worker）
	docker compose up -d

up-full: ## 启动全部服务（含 Ollama + 监控）
	docker compose --profile full --profile monitor up -d

down: ## 停止所有服务
	docker compose --profile full --profile monitor down

restart: ## 重启 API 服务（代码更新后）
	docker compose restart api celery_worker

logs: ## 查看 API 实时日志
	docker compose logs -f api

logs-worker: ## 查看 Worker 实时日志
	docker compose logs -f celery_worker

seed: ## 灌入 demo 数据（demo@example.com / demo123456）
	docker compose exec api python scripts/seed_demo_data.py

test: ## 运行 pytest 测试
	docker compose exec api pytest tests/ -v

shell: ## 进入 API 容器 shell
	docker compose exec api bash

ollama-pull: ## 拉取 Ollama 模型（bge-m3 + qwen2.5）
	@echo "拉取 bge-m3 向量模型..."
	docker compose exec -T ollama ollama pull bge-m3
	@echo "拉取 qwen2.5:3b 对话模型..."
	docker compose exec -T ollama ollama pull qwen2.5:3b

db-shell: ## 进入 PostgreSQL 命令行
	docker compose exec db psql -U postgres -d fastapi_db

redis-cli: ## 进入 Redis 命令行
	docker compose exec redis redis-cli

clean: ## 清理所有容器和数据卷（⚠️ 会删除数据库）
	docker compose --profile full --profile monitor down -v
	@echo "清理完成。运行 make setup 重新开始。"
