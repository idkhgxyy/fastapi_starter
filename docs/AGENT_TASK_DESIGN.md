# Agent 任务（目标 → 成果）设计草案

> 状态：已实现并上线（2026-10-21）。产出 Markdown + 支持导出下载；资料范围用开关切换「自动检索全部 / 指定文档」；入口为侧边栏「任务」下分「待办 / 目标成果」两个子标签。

## 1. 要解决的问题

当前 `tasks` 表只是待办清单：标题、描述、状态，没有"目标"，也没有"产出"。
本设计的核心命题是：

> 用户描述一个目标，系统结合**知识库材料**与**已有能力**，产出一份可用的成果。

一句话区分：现在的任务回答"我要做什么"，Agent 任务回答"我要得到什么"。

## 2. v1 范围（薄切片）

**做：**

- 输入：目标描述 + 资料范围（不选 = 全部知识库）+ 产出类型（v1 只有 Markdown 报告）
- 执行：Celery 异步，**固定流水线**（采集 → 生成 → 落库），不做开放式自主规划
- 输出：一份 Markdown 成果，存库，可在页面预览 / 复制 / 下载
- 状态：`pending → running → succeeded / failed`，失败记录原因，支持整体重试
- 成本：受用户月度预算约束；单任务设置 token 上限；每次调用记账

**不做（明确排除）：**

- Agent 自己决定步骤（自主规划）
- 联网搜索、调用外部 API
- 生成 docx/pdf 等二进制文件
- 定时/触发式任务
- 断点续跑（v1 失败只能整任务重试）

## 3. 数据模型

```text
agent_tasks
  id, user_id(FK users, CASCADE), title, goal(Text)
  status: pending | running | succeeded | failed
  scope_document_ids(JSON, null = 全部已就绪文档)
  output_type: markdown
  result_markdown(Text, null)
  error_message(Text, null)
  prompt_tokens, completion_tokens, cost_cny      # 任务级汇总
  created_at, started_at, finished_at

agent_task_steps                                # 让进度可见、成本可归因
  id, task_id(FK agent_tasks, CASCADE)
  seq, name(retrieve | outline | write | finalize)
  status: pending | running | succeeded | failed
  summary(Text)                                  # 这一步做了什么（给用户看）
  prompt_tokens, completion_tokens, cost_cny
  started_at, finished_at
```

复用现有资产：

- 材料：`documents` / `document_chunks` / `document.summary`
- 成本：`llm_call_logs`（新增 endpoint 值 `/agent-task`）+ `estimate_cost_cny`
- 预算：`check_budget`（创建任务前拦截，执行中每次调用后再查一次）
- 执行：Celery worker + `SessionLocal`（与 `worker/tasks.py` 一致）

## 4. 执行流程

```text
POST /agent-tasks
  → check_budget 拦截
  → 建 agent_tasks(pending) + steps 骨架
  → 投递 Celery 任务
  → 返回 task_id

Worker:
  1. retrieve  选定范围内取每篇文档的 summary（没有摘要则取首段）
               + 按 goal 检索 top-N 片段，按 token 预算截断
  2. outline   一次 LLM 调用生成报告大纲（可关闭）
  3. write     按大纲分节生成（每节一次调用，控制单次 max_tokens）
  4. finalize  合并、加来源标注、写回 result_markdown
  5. 汇总 tokens/cost 到 agent_tasks，状态置 succeeded
```

失败处理：任一步异常 → `steps` 与 `agent_tasks` 置 failed，保留已完成的部分内容与错误信息。
预算触顶：后续步骤不再发起 LLM 调用，任务标记 failed，错误信息写明"已达到预算上限"。

## 5. 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/agent-tasks` | 创建并投递 |
| GET | `/api/v1/agent-tasks` | 列表（状态、时间、成本） |
| GET | `/api/v1/agent-tasks/{id}` | 详情：步骤时间线 + Markdown 成果 |
| POST | `/api/v1/agent-tasks/{id}/retry` | 仅 failed 可重试 |
| DELETE | `/api/v1/agent-tasks/{id}` | 删除任务与步骤 |

鉴权与租户隔离与现有接口一致（`get_current_active_user` + `owner_id` 过滤）。

## 6. 前端

- 侧边栏第三个标签改名为「任务」，内部两个子标签：**待办**（现有 TasksPanel）/ **目标成果**（新）
- 新建表单：目标（多行）、资料范围（多选文档，默认全选）、生成按钮
- 列表：状态点 + 标题 + 成本 + 时间
- 详情：步骤时间线（retrieve → outline → write → finalize）、Markdown 预览、复制/下载、失败原因与重试
- 进度：**轮询 3 秒**（复用知识库面板已有模式），不做 SSE

## 7. 与现有能力的联动

| 联动 | 方案 |
|---|---|
| 目标 ↔ 知识库 | 执行时读取选定文档的摘要与片段，成果中标注来源文档 |
| 目标 ↔ 成本治理 | 创建前预算拦截、执行中逐次记账、任务级汇总；超限中止 |
| 目标 ↔ 可观测性 | 每次 LLM 调用写入 `llm_call_logs`，endpoint 带任务 id，可归因 |
| 目标 ↔ 对话（v2） | 注册 `create_agent_task` 工具，聊天里直接下达目标；v1 只做页面入口 |
| 目标 ↔ 会话（v2） | 任务可关联 conversation_id，把成果回写成一条消息；v1 不做 |

## 8. 成本与风险

- **单任务调用次数**：v1 为 3~6 次（大纲 + 3~4 节 + 收尾），预估 1~2 万 token，**约 ¥0.03~0.10/任务**
- **成本护栏**：单任务 token 上限（配置项）、每步 max_tokens、执行中复查预算
- **质量风险**：固定流水线比自主规划可靠，但仍可能出现"材料里没有却编造" → 提示词强制要求标注来源、无依据时写"资料未覆盖"
- **长文本风险**：分节生成时各节之间可能重复/冲突 → v1 接受，先看实际效果
- **2G 服务器**：全程云端 API，无本地模型，内存压力可忽略；主要压力是 LLM 延迟（单任务可能 1~3 分钟）

## 9. 里程碑

| 阶段 | 内容 | 预估 |
|---|---|---|
| M1 | 两张表 + 迁移 + 创建/列表/详情接口 + 单次调用生成报告 | 一轮 |
| M2 | 分步执行 + 进度时间线 + 成本汇总 + 重试 | 一轮 |
| M3 | 对话里用工具下达目标 | 半轮 |
| M4 | 导出 docx/pdf、分享 | 可选 |

## 10. 评审结论（2026-10-21）

1. **产出**：v1 只生成 Markdown，但必须支持**导出下载**（本地查看）。
2. **资料范围**：两种都做，用开关切换——「自动检索全部已就绪文档」/「手动勾选文档」。
3. **入口**：侧边栏第三个标签改名为「任务」，内部两个子标签：待办（现有）/ 目标成果（新）。

## 11. 原待拍板问题（已决议）

1. **v1 产出只有 Markdown 报告，够不够？**（还是必须能导出文件）
2. **资料范围**：默认"自动检索全部"还是"必须手动勾选"？（建议默认全部 + 可勾选）
3. **入口位置**：第三个标签改名「任务」下分两个子标签（推荐），还是新增第四个标签「成果」？
