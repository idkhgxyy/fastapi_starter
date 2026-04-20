#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "[bootstrap] 已根据 .env.example 创建 .env"
fi

echo "[bootstrap] 启动基础服务..."
docker compose up -d --build

echo "[bootstrap] 等待 Ollama 就绪..."
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  sleep 2
done

echo "[bootstrap] 拉取本地模型 qwen2.5:3b ..."
docker compose exec -T ollama ollama pull qwen2.5:3b

echo "[bootstrap] 拉取向量模型 bge-m3 ..."
docker compose exec -T ollama ollama pull bge-m3

echo "[bootstrap] 初始化完成。"
echo "API Docs:      http://localhost:8000/docs"
echo "Prometheus:    http://localhost:9090"
echo "Grafana:       http://localhost:3000"
