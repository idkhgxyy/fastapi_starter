# 默认使用华为云 SWR 代理镜像（国内加速），CI 环境可通过 BASE_IMAGE 构建参数切换
ARG BASE_IMAGE=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim

# ============================================
# Stage 1: 构建前端
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
# 国内镜像源加速（海外构建可通过 --build-arg 覆盖或还原）
RUN npm config set registry https://registry.npmmirror.com \
    && (npm ci --prefer-offline 2>/dev/null || npm install)
COPY frontend/ .
RUN npm run build

# ============================================
# Stage 2: 构建后端 + 前端产物
# ============================================
FROM ${BASE_IMAGE}

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 设置工作目录
WORKDIR /app

# 国内镜像源加速：debian apt 换腾讯镜像（与 BASE_IMAGE 的华为云代理配套）
RUN sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list 2>/dev/null; \
    true

# 安装系统依赖；curl 用于容器健康检查，libpq-dev 用于 PostgreSQL 驱动编译
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（pip 走清华镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端代码
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/

# 从前端构建阶段复制产物到静态文件目录
COPY --from=frontend-builder /frontend/dist app/static/

# 暴露 FastAPI 运行端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
