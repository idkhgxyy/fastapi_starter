#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}[1/5] 初始化 .env 配置...${NC}"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo -e "${GREEN}  ✓ 已根据 .env.example 创建 .env${NC}"

  # 自动生成安全的 SECRET_KEY
  if command -v openssl &>/dev/null; then
    NEW_SECRET=$(openssl rand -hex 32)
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s/^SECRET_KEY=.*/SECRET_KEY=${NEW_SECRET}/" .env
    else
      sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${NEW_SECRET}/" .env
    fi
    echo -e "${GREEN}  ✓ 已自动生成随机 SECRET_KEY${NC}"
  else
    echo -e "${YELLOW}  ⚠ openssl 未安装，SECRET_KEY 使用默认值（生产环境请替换）${NC}"
  fi
else
  echo -e "${GREEN}  ✓ .env 已存在，跳过${NC}"
fi

echo -e "${CYAN}[2/5] 启动核心服务 (API + DB + Redis + Worker)...${NC}"
docker compose up -d --build

echo -e "${CYAN}[3/5] 等待 API 服务就绪...${NC}"
MAX_WAIT=60
WAITED=0
until curl -sf http://localhost:8000/api/v1/health >/dev/null 2>&1; do
  sleep 2
  WAITED=$((WAITED + 2))
  if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}  ⚠ API 服务启动超时，请检查: docker compose logs api${NC}"
    break
  fi
done
if [ $WAITED -lt $MAX_WAIT ]; then
  echo -e "${GREEN}  ✓ API 服务已就绪${NC}"
fi

echo -e "${CYAN}[4/5] 灌入 Demo 数据...${NC}"
docker compose exec -T api python scripts/seed_demo_data.py 2>/dev/null || \
  echo -e "${YELLOW}  ⚠ Demo 数据灌入失败，可稍后手动执行: make seed${NC}"

echo -e "${CYAN}[5/5] 检查 Ollama 可用性...${NC}"
if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo -e "${GREEN}  ✓ Ollama 已运行${NC}"

  # 检查是否已拉取 bge-m3 模型
  if docker compose exec -T ollama ollama list 2>/dev/null | grep -q "bge-m3"; then
    echo -e "${GREEN}  ✓ bge-m3 模型已就绪${NC}"
  else
    echo -e "${YELLOW}  → 拉取 bge-m3 向量模型（首次需要下载，请耐心等待）...${NC}"
    docker compose exec -T ollama ollama pull bge-m3 || \
      echo -e "${YELLOW}  ⚠ 模型拉取失败，可稍后手动执行: make ollama-pull${NC}"
  fi
else
  echo -e "${YELLOW}  ⚠ Ollama 未运行，RAG 功能暂不可用${NC}"
  echo -e "${YELLOW}    启动完整服务: make up-full${NC}"
  echo -e "${YELLOW}    拉取模型后:   make ollama-pull${NC}"
fi

# 判断是否为 Mock 模式
LLM_KEY=$(grep -E "^LLM_API_KEY=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
if [ -z "$LLM_KEY" ]; then
  MOCK_MODE="${YELLOW}Mock 模式（无 API Key，使用预设回复）${NC}"
else
  MOCK_MODE="${GREEN}真实 LLM 模式${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🚀 FastAPI Starter 启动完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  LLM 模式:    ${MOCK_MODE}"
echo ""
echo -e "  API Docs:     ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  ReDoc:        ${CYAN}http://localhost:8000/redoc${NC}"
echo -e "  Prometheus:   ${CYAN}http://localhost:9090${NC}"
echo -e "  Grafana:      ${CYAN}http://localhost:3000${NC} (admin/admin)"
echo -e "  Flower:       ${CYAN}http://localhost:5555${NC}"
echo ""
echo -e "  Demo 账号:    ${CYAN}demo@example.com / demo123456${NC}"
echo ""
echo -e "  常用命令:"
echo -e "    ${CYAN}make help${NC}         查看所有命令"
echo -e "    ${CYAN}make logs${NC}         查看 API 日志"
echo -e "    ${CYAN}make up-full${NC}      启动全部服务（含 Ollama + 监控）"
echo -e "    ${CYAN}make ollama-pull${NC}  拉取 Ollama 模型"
echo ""
