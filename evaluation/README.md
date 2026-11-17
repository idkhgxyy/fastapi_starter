# RAG 评测集

用真实知识库问题量化检索和语义缓存改动，不依赖 LLM 打分。

## 文件

- `rag_eval_set.jsonl`：27 条检索题，覆盖 4 篇 arXiv 和 15 篇雅思/课设/JD。
- `rag_cache_eval_set.jsonl`：8 组缓存对照，每组包含同义改写（应命中）和负数（应拒绝）。
- `answer_eval_set.jsonl`：13 条答案质量题，检查回答是否包含预期事实。
- `synth/`：6 篇固定合成文档 + 20 道分层题 + 8 组缓存对照，用于全链路回归。
- `../scripts/rag_eval.py`、`../scripts/answer_eval.py`、`../scripts/eval_pipeline.py`：runner。

## 运行

```bash
# 完整评测（检索 + 缓存）
docker compose exec -w /app -e PYTHONPATH=/app api python scripts/rag_eval.py

# 只跑检索，或只跑前 10 条
docker compose exec -w /app -e PYTHONPATH=/app api python scripts/rag_eval.py --skip-cache --limit 10
```

需要真实知识库和 embedding Key；缺失的用户/文档会打印 `SKIP`。缓存评测使用临时 SQLite，不读写线上 `qa_cache_entries`；灰区负数会触发一次短 LLM 校验。

## 指标

- `recall@k`：期望文档是否出现在 top-k 检索结果。
- `MRR`：第一个期望文档的倒数排名。
- `keyword_hit`：期望文档的 top-k 片段是否包含任一期望关键词。
- `evidence_hit`：同时满足文档命中与关键词命中。
- `cache paraphrase_hit`：同义改写命中率。
- `cache negative_reject`：换实体/数字/多意图的拒绝率。

## 基线（2026-10-27）

- 检索：n=27，recall@3=1.00，MRR=0.963，keyword_hit=1.00，evidence_hit=1.00。
- 缓存：pairs=8，paraphrase_hit=1.00，negative_reject=1.00。

改检索、切块或缓存逻辑后重跑，对比这两行即可。新增/修改文档时同步更新 `expected_documents` 的文件名。

## 答案质量

```bash
make answer-eval
# 或
docker compose exec -w /app -e PYTHONPATH=/app api python scripts/answer_eval.py
```

直接调用 `RAGService` + 真实 LLM，检查回答中的事实关键词；不经过 HTTP/缓存，也不写 `llm_call_logs`。基线（2026-10-27）：13 题，source_hit=1.00，answer_hit=1.00，平均 2315ms，总成本约 ¥0.054。它验证的是“检索内容能否被正确复述”，不是通用回答质量或事实推理能力。

## 合成知识库全链路评测

固定 6 篇合成文档 + 20 道分层题 + 8 组缓存对照，走完整 HTTP/Celery 链路：清空评测账号 → 上传并等 ready → 检索 → 回答 → 缓存 → 流式，最后落盘报告。

```bash
make eval-pipeline
# 或
docker compose exec -w /app -e PYTHONPATH=/app -e EVAL_GIT_COMMIT=$(git rev-parse --short HEAD) \
  api python scripts/eval_pipeline.py --strict
```

- 语料：`synth/corpus/`，包含 J106366 / J101366 近编号干扰、P-2201/P-2202 跨文档事实和 3 道负例题。
- 题集：`synth/eval_set.jsonl`，按 `basic` / `paraphrase` / `near-id` / `cross-doc` / `negative` 分层。
- 缓存：`synth/cache_pairs.jsonl`，每组含改写（应命中）和换实体负例（应拒绝）。
- 报告：`runs/<run_id>/report.json` 与 `report.md`，包含 commit、LLM/embedding 模型、top_k、成本、失败明细，并自动对比上一轮。

判定口径：检索或答案失败、缓存负例误命中、流式缺 `[DONE]`/来源事件都算硬失败；改写未命中只计入指标，不算硬失败。答案层每题前会清空该账号缓存，避免题目之间互相污染；缓存层单独清空后重新种入。评测账号默认 `eval-synth@example.com`，密码复用 `SMOKE_PASSWORD`（可用 `EVAL_PASSWORD` 覆盖）。

负例归因（2026-11-17 起）：每组负例额外记录 `negative_similarity`（与组内候选的最大余弦相似度，向量直接读缓存条目——路由把同一条 query_vector 传给 lookup 和 store，零额外 embedding 调用）和 `negative_reject_reason`，把 `negative_reject_rate` 按机制拆开：`below_candidate`（相似度未达 0.80，embedding 确定性拒绝）、`guard`（数字/来源守卫，确定性拒绝）、`llm_judge`（灰区 LLM 判否，概率性拒绝，附本轮校验真实响应）、`other`（缓存外因素，如校验故障被静默按不命中——是故障不是安全，需排查）、`hit`（误命中）。注意数字/专名守卫只认 ASCII token：纯中文实体替换（年假→病假、星河→远山）没有静态防线，相似度一旦 ≥0.95 就是必然误命中，只能靠灰区 LLM 兜底；看负例拒绝率时必须看归因拆分，不能只看总数。

局限：语料和题目都是自造的，只能证明链路是否退化，不能代表真实使用质量。跨轮比较前先确认报告里的 `git_commit`、模型和 `top_k` 一致；换语料后不与旧报告直接可比。

运行环境：**默认在本地 compose 跑，不要在生产服务器跑完整评测。** 生产机是 2C2G，Folio 四容器 + QQ bot 常驻已占约 1.0GB 内存、swap 已用约 500MB；评测峰值会再叠加约 250–350MB（脚本进程 + Celery 处理 + API 查询），余量偏薄，且会向线上库写入文档、缓存和调用日志。生产链路健康检查用 `make smoke`。另外线上 embedding 是 `text-embedding-v4`、本地是 `bge-m3`，两边的报告分数不能直接横比。

### 基线（2026-11-12，commit 5859654）

- 导入：6 篇 / 12 chunks，全部 ready。
- 检索：n=17，recall@3=1.00，MRR=1.000，keyword_hit=1.00。
- 答案：n=20，pass=1.00，source_hit=1.00，平均 4530ms。
- 缓存：pairs=8，paraphrase_hit=0.625，negative_reject=1.00，8 组 base 均无污染。
- 流式：2/2，`[DONE]` 收尾与来源事件正常。
- 成本：¥0.1012，耗时 303s（deepseek-flash + bge-m3，top_k=3）。结论 **pass**。

本轮同时验证了本地镜像重建后的依赖升级（fastapi 0.128.8 / SQLAlchemy 2.0.57 / pydantic 2.13.5）没有引入退化：`app/` 与旧基线 commit `33ffe52` 完全一致，唯一变量是依赖版本。

缓存改写仍有 3 组未命中：星河预算、期末占比、J108810 框架（相似度低于 0.80 候选下限，报告里 `sim=None`）。这是当前召回缺口，不是断言失败；改缓存守卫或 embedding 后用它验证是否补齐。

**缓存层隔离修复（2026-11-12）**：原先 `invalidate_user_cache` 只在整层开头调用一次，组间不清缓存。`cache-sick-leave` 的 negative（"带薪年假"）与 `cache-annual-leave` 的 base 几乎同句，于是命中了第 3 组早先种入的条目，`negative_reject` 假性掉到 0.875、`base_cached_unexpectedly=true`。已改为每组前清缓存，修复后 8 组污染信号全为 false、负例全部正确拒绝。**因此 2026-10-29 那轮的缓存指标不可与本轮直接横比**；检索/答案/流式三层不受该修复影响，仍可比。

### 负例归因首轮（2026-11-17，本地 bge-m3 + deepseek-flash，top_k=3）

总指标与 2026-11-12 基线一致（检索/答案/流式全 1.00，改写命中 0.625，负例拒绝 1.00，成本 ¥0.0987，结论 pass），但负例拒绝 1.00 拆开后是 **below_candidate 4 / guard 1 / llm_judge 3 / other 0 / hit 0**：

- 真正靠静态守卫的只有 `cache-106366-language`（sim=0.958，已进直通带，数字守卫拦下）。`cache-2201-budget`（0.7884）与 `cache-108810-framework`（0.685）的负例相似度未达 0.80，是 embedding 拒的，守卫没出手——只看总数会误以为它们也是守卫的功劳。
- 3 对概率性拒绝全是纯中文实体替换：annual-leave 0.8469、final-weight 0.934、sick-leave 0.9409，本轮 LLM 均判「否」。**最薄余量 0.009**（sick-leave 距 0.95 直通带），其次 0.016（final-weight）。中文实体替换没有静态守卫，相似度越线即必然误命中；换 embedding 模型或措辞微调都可能越线。
- 星河/远山两对中文负例相似度 0.68/0.61，embedding 确定性拒——"中文负例全走 LLM"不成立，要按组看。
- 是否给中文实体替换补直通带防线（强制灰区校验或中文差异启发式）尚未决策：前者让中文直通命中全部多一次短 LLM 调用，后者误伤合法改写；先积累归因数据再定。

## 部署后冒烟

评测集验证检索/缓存内部，不覆盖 HTTP、登录、上传、Celery 和流式。部署后另跑：

```bash
make smoke
# 服务器上：
sudo docker exec -w /app -e PYTHONPATH=/app fastapi-starter-api python scripts/smoke_test.py
```

脚本使用专用 `smoke@example.com` 账号（首次自动注册；`SMOKE_PASSWORD` 必须由环境变量或本地 `.env` 提供，脚本不内置默认密码），上传一篇唯一事实的临时文档，验证健康检查、ready、真实 RAG、缓存命中、换数字拒绝、流式 `[DONE]` 和清理；任何一步失败返回非 0。

浏览器层（需本机 Playwright）：

```bash
# 服务器前端只监听 127.0.0.1，先建隧道
ssh -N -L 18081:127.0.0.1:8000 ubuntu@YOUR_SERVER
UI_SMOKE_BASE_URL=http://127.0.0.1:18081 /usr/bin/python3 scripts/ui_smoke_test.py
```

覆盖登录页、侧栏上传到“就绪”、知识库搜索、知识库问答与来源、对话框提问、流式结束和清理；失败/成功截图写到 `evaluation/artifacts/`（gitignored）。
