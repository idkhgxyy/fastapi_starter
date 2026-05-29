# FastAPI Starter — 项目改进建议

> 针对 **Agent 开发岗** 简历项目优化，按优先级排列。

---

## 🔴 P0 — 建议面试前修掉

### 1. 替换 `eval()` 为安全数学计算

**问题位置：** `app/services/llm_service.py` — `calculate()` 工具函数

**现状：** 使用受限 `eval()`（`__builtins__` 置空，仅允许 `abs/round/min/max/pow`）。

**风险：** 虽然做了限制，但面试官很容易追问 eval 的安全问题。如果对方是 Python 背景较强的面试官，这可能成为减分项。

**建议方案：** 替换为 `ast.literal_eval` + 简单的运算符解析，或引入轻量库 `pyexpr`。改动很小但安全等级提升明显。

```python
# 替代方案示例：使用 ast 安全解析简单数学表达式
import ast
import operator

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Call: None,  # 单独处理 abs/round/min/max
}

def safe_eval(expr: str) -> float:
    """安全计算数学表达式，不使用 eval()"""
    node = ast.parse(expr.strip(), mode="eval").body
    return _safe_eval_node(node)
```

---

### 2. 给 LLM 调用添加 Mock/Fallback 机制

**问题位置：** `app/services/llm_service.py`、`app/services/rag_service.py`

**现状：** LLM API（Ollama/DeepSeek）不可用时，系统直接报错。

**建议方案：** 增加一个简单的 MockLLMClient 模式（通过环境变量 `LLM_MOCK=true` 开启），返回预设的回复。好处：
- 面试时可以演示项目而无需依赖外部 API
- CI 测试不需要 API Key
- 展示你有"系统降级"的设计意识

---

### 3. 优化启动验证逻辑

**问题位置：** `app/main.py` — `lifespan` 函数

**现状：** 启动时检查 SECRET_KEY 是否为默认值、LLM_API_KEY 是否为空。

**建议：** 补充更细粒度的验证：
- 增加检查 DB 连接是否真的可用（不只是 `create_all` 不报错）
- 增加 Redis 连接检查
- 检查 pgvector extension 是否已安装（因为 RAG 依赖它）

```python
# 补充数据库可用性检查
try:
    db = next(get_db())
    db.execute(text("SELECT 1"))
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    raise
```

---

## 🟡 P1 — 大幅提升面试竞争力

### 4. 对接 MCP 协议（强烈推荐 ⭐）

**建议位置：** `app/services/mcp_service.py`（新建）

**为什么加分：** MCP（Model Context Protocol）是 2024-2025 年 Agent 方向最热门的协议规范，由 Anthropic 提出。如果你能展示"主动了解并落地了 MCP"，面试官会认为你有技术敏锐度。

**怎么做：** 把现有的 5 个 Tool（天气、创建任务、系统状态、列出任务、计算器）封装成 MCP Tool 格式。

```python
# mcp_service.py — 概念示例
from typing import Any
from pydantic import BaseModel

class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]

class MCPService:
    """MCP 协议适配层 — 将内部 Tool 暴露为标准 MCP Tool"""
    
    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="get_current_weather",
                description="获取指定城市的当前天气",
                input_schema={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称"}
                    },
                    "required": ["location"]
                }
            ),
            # ... 其他工具
        ]
    
    async def call_tool(self, name: str, args: dict) -> Any:
        """统一工具调用入口（路由到对应服务方法）"""
        ...
```

只需要几十行代码，面试时就可以说：
> "我把系统设计成了 MCP 兼容架构，模型层的工具可以跨平台复用，不绑定特定 Agent 框架。"

---

### 5. 补充一个 Supervisor Agent 概念（口头/代码均可）

**现状：** 系统只有一个 Chat Agent，直接处理所有用户请求。

**建议：** 在现有系统上做一个轻量的"Agent 路由"概念：

```
用户输入 → Supervisor Agent（判断意图）
              ├── RAG Agent → 知识库问答
              ├── Tool Agent → 工具调用/任务执行
              ├── Chat Agent → 普通对话
              └── Task Agent → 任务管理
```

**代码实现建议：** 在 `app/services/` 下新增 `agent_router.py`，用一个小 LLM 调用判断意图类型，然后路由到对应 handler。成本低、效果好。

面试时展示这个设计，说明你有 Agent **架构设计** 的思考，而不只是实现了单个 Agent 功能。

---

## 🟢 P2 — 小修小补

### 6. `security.py` 导入顺序

**问题位置：** `app/core/security.py` 第31行附近

**现状：** `from typing import Optional` 出现在函数定义之后。

**建议：** 移到文件顶部，保持 PEP8 规范。

### 7. 补充 LLM 调用的速率限制提示

**现状：** 已实现基于 Redis 的 API 速率限制，但 LLM 调用本身没有限流。

**建议：** 在 `llm_service.py` 中对 LLM API 调用增加退避/重试机制（可以用 `tenacity`），当 API 返回 429 时自动等待。

### 8. `.env.example` 增加注释和示例值

**现状：** `.env.example` 有占位符但没有说明每个字段的取值范围。

**建议：** 增加每行的注释，特别是 `DATABASE_URL` 的格式说明和 `LLM_PROVIDER` 的可选值。

---

## 📋 改进优先级总结

| 优先级 | 事项 | 预估工时 | 面试影响力 |
|--------|------|----------|------------|
| 🔴 P0 | 替换 eval() 为安全方案 | 1h | 高（避坑） |
| 🔴 P0 | LLM Mock/Fallback 机制 | 2h | 高 |
| 🔴 P0 | 启动验证增强 | 1h | 中 |
| 🟡 P1 | 接入 MCP 协议 | 3h | **非常高** |
| 🟡 P1 | Agent Router 概念 | 2h | 高 |
| 🟢 P2 | 小修补（导入/限流/env） | 1h | 低 |

---

## 💡 面试话术建议

当面试官问"介绍一下你的 Agent 项目"时，建议按照以下结构展开：

1. **一句话定调：** "我做的是一个生产级 FastAPI AI Agent 后端，不只是聊天套壳，而是实现了完整的工具调用管线、用户隔离的 RAG、异步任务和可观测体系。"

2. **讲设计思路（30秒）：** "核心设计是两轮 Tool Calling —— 第一轮 LLM 判断需要调用什么工具，系统执行后将结果注入第二轮推理。这样做的好处是 LLM 不需要一次性生成完整回复，中间步骤可审计。"

3. **讲 RAG 亮点（20秒）：** "RAG 部分我做了按用户隔离、多格式文档支持、pgvector 检索 + BGE-Reranker 可选重排，以及完整的状态机管理（排队→处理中→就绪→失败）。"

4. **讲工程化（20秒）：** "补了 121 个单元测试、CI、Docker Compose、Prometheus/Grafana 监控，还有一个自建的 LLM 调用日志模块追踪每次调用的 token/耗时/成本。"

5. **收尾升华：** "这个项目让我对 Agent 工程化落地有了完整的理解——从 LLM 推理到工具调度、从数据隔离到可观测性，每个环节都有设计取舍。"
