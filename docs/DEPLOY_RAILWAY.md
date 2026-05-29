# Railway 部署教程

> 把你的 FastAPI Starter 项目部署到线上，面试官直接点开网址就能用。

---

## 一、准备工作

### 1.1 需要一个云端 LLM API

部署到线上后没有 Ollama 了，你需要换成一个云端大模型。推荐：

| 服务商 | 免费额度 | 接入方式 |
|--------|----------|----------|
| **DeepSeek** | 注册送 500 万 token | OpenAI 兼容，`base_url` 填 `https://api.deepseek.com` |
| **阿里云百炼** | 注册送 100 万 token | OpenAI 兼容，`base_url` 填对应区域的网关地址 |
| **SiliconFlow** | 注册送 200 万 token | 支持 Qwen2.5 免费模型，`base_url` 填 `https://api.siliconflow.cn/v1` |

先注册一个拿到 `API Key` 和 `BASE_URL`。

### 1.2 需要的东西

- ✅ 一个 GitHub 账号
- ✅ 代码已推到 GitHub 仓库
- ✅ 一个 [Railway](https://railway.app) 账号（用 GitHub 登录即可，不需要绑卡也能部署，但绑卡后可享受更稳定的免费额度）
- ✅ 上面拿到的云端 LLM API Key

---

## 二、部署步骤

### 2.1 创建 Railway 项目

1. 打开 [Railway](https://railway.app) 并用 GitHub 登录
2. 点击 **New Project**
3. 选择 **Deploy from GitHub repo**
4. 授权 Railway 访问你的 `fastapi-starter` 仓库
5. 选择仓库后，Railway 会自动检测到 `Dockerfile` 并开始构建

### 2.2 添加 PostgreSQL 数据库

1. 在项目页面点击 **New** → **Database** → **PostgreSQL**
2. Railway 的 PostgreSQL 自带 pgvector 扩展，不用额外配置
3. 创建完成后，点击 PostgreSQL 服务，在 **Connect** 标签页可以看到 `DATABASE_URL`（格式类似 `postgresql://postgres:xxx@xxx.railway.app:5432/railway`）

### 2.3 添加 Redis

1. 点击 **New** → **Database** → **Redis**
2. 创建完成后，记录下连接信息（Redis 服务详情页里能看到 `REDIS_URL`）

### 2.4 配置环境变量

1. 点击 API 服务（就是你的 Web 服务）
2. 进入 **Variables** 标签页
3. 添加以下环境变量：

```text
DATABASE_URL=从 PostgreSQL 服务复制过来
REDIS_URL=从 Redis 服务复制过来
SECRET_KEY=生成一个随机密钥（可以用 openssl rand -hex 32）
LLM_API_KEY=你申请到的云端 API Key
LLM_BASE_URL=你用的服务商地址（如 https://api.deepseek.com/v1）
LLM_MODEL_NAME=模型名（如 deepseek-chat 或 Qwen/Qwen2.5-72B-Instruct）
EMBEDDING_MODEL_NAME=bge-m3
LLM_PROVIDER=你的服务商名字
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://*.railway.app
LOG_FORMAT=text
```

**注意：**
- `DATABASE_URL` 和 `REDIS_URL` 不用手动填——Railway 会自动把数据库连接信息注入给同项目下的 Web 服务。但为了保险，可以手动粘贴确认
- `SECRET_KEY` 务必改为一个强随机字符串，不要用默认值

### 2.5 修改启动命令（关键）

Railway 默认会用 Dockerfile 里的 `CMD` 启动，但我们需要先执行数据库迁移。

在你的 `Dockerfile` 中，把最后一行：

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

改成：

```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

`$PORT` 是 Railway 自动注入的环境变量，表示服务监听的端口。

### 2.6 部署

1. 把改好的代码 push 到 GitHub
2. Railway 会自动重新部署（或者点 **Deploy** 按钮手动触发）
3. 等待构建完成（第一次构建可能需要 2-5 分钟）
4. 构建成功后，Railway 会给你的服务分配一个 `*.railway.app` 域名
5. 点击域名访问，看到 `Welcome to FastAPI Starter` 就成功了

部署后的访问地址：
- **API**: `https://你的项目名.up.railway.app`
- **Swagger**: `https://你的项目名.up.railway.app/docs`
- **Metrics**: `https://你的项目名.up.railway.app/metrics`

---

## 三、添加 Celery Worker（可选但有更好）

如果希望异步文档处理也能工作，需要把 Worker 单独部署为一个服务：

1. 在同一个 Railway 项目下，点击 **New** → **Web Service** → 选择同一个仓库
2. 在 **Deploy** 页面修改启动命令为：

```bash
celery -A app.worker.celery_app worker --loglevel=info
```

3. 为该服务配置同样的环境变量（DATABASE_URL、REDIS_URL 等）
4. 点击部署

这样 API 和 Worker 共享同一个 Redis 和 PostgreSQL，API 投递任务，Worker 消费。

---

## 四、验证部署

部署完成后，在浏览器里测试：

```bash
# 1. 健康检查
curl https://你的域名.up.railway.app/api/v1/health

# 2. 注册用户
curl -X POST https://你的域名.up.railway.app/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","email":"demo@test.com","password":"demo123456"}'

# 3. 登录
curl -X POST https://你的域名.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@test.com&password=demo123456"

# 4. 打开 Swagger（浏览器直接点）
# https://你的域名.up.railway.app/docs
```

---

## 五、常见问题

### 5.1 部署失败 / 构建超时

- 检查是否在免费额度内（新用户有 $5，够跑一个月）
- 如果构建时卡在 `pip install`，可以把 `requirements.txt` 里的包指定更宽松的版本
- Railway 默认使用 amd64 架构，和 Dockerfile 保持一致

### 5.2 数据库迁移报错

- 检查 `DATABASE_URL` 是否正确
- 迁移文件顺序错误的话，可以手动重置：
  ```bash
  # 登录到 Railway 的 Web 终端
  alembic downgrade base
  alembic upgrade head
  ```

### 5.3 启动后访问报 503 / 502

- 检查启动日志（Railway 页面上的 **Deploy Logs**）
- 常见原因：`SECRET_KEY` 还是默认值，导致启动校验失败
- 数据库连接超时：看看 `DATABASE_URL` 格式对不对

### 5.4 文档上传后一直卡在 queued

- 说明 Celery Worker 没起来或不工作
- 检查 Redis 连接是否正常
- 检查 Worker 的日志

### 5.5 免费额度不够用怎么办？

Railway 免费版每月 $5 额度，对于这个项目：
- 1 个 Web Service（API）：~$2-3/月（低流量）
- 1 个 PostgreSQL：免费
- 1 个 Redis：~$0.5/月
- 总量：约 $3.5/月，在免费额度内

如果跑 Worker，大概再加 $1-2。总费用仍在 $5 以内。

注意：如果不绑卡，免费额度更少且服务可能会休眠。建议**绑定信用卡**（不会乱扣费，有消费上限控制）。

### 5.6 域名不好看怎么办？

Railway 自动分配的域名是 `xxx.up.railway.app` 格式，可以在服务设置里 **Generate Domain** 自定义前缀。

---

## 六、总结

部署后的变化：

| | 本地开发 | 线上部署 |
|--|---------|---------|
| 大模型 | Ollama（本地）| 云端 API（DeepSeek 等） |
| 数据库 | Docker PostgreSQL | Railway PostgreSQL |
| Redis | Docker Redis | Railway Redis |
| 访问地址 | localhost:8000 | xxx.up.railway.app |
| 文档处理 | Celery Worker | 可选部署 Worker |

整个部署过程大概 **20 分钟**。部署成功后，你的 README 里就可以加一行：

> 🌐 **在线体验**: [https://你的域名.up.railway.app/docs](https://你的域名.up.railway.app/docs)

这对面试来说，比任何代码截图都有说服力。
