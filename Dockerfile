# 使用华为云 SWR 代理镜像，避免当前网络环境下访问 Docker Hub 失败
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 设置工作目录
WORKDIR /app

# 安装系统依赖；curl 用于容器健康检查，libpq-dev 用于 PostgreSQL 驱动编译
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制整个项目代码到容器中
COPY . .

# 暴露 FastAPI 运行端口
EXPOSE 8000

# 启动命令（默认用 uvicorn，生产环境通常推荐 gunicorn 配合 uvicorn worker，这里为了保持 starter 简单先用 uvicorn）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
