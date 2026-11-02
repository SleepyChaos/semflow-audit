# 实验执行入口与共享内核

## 目标与模块边界

Web/Celery 和 CLI 共用 `app/runtime/` 中的扫描、阶段执行入口，业务仍由已有
LangGraph 图、services、ports/adapters 和持久化模块实现。CLI 不启动 HTTP 服务、
Worker 或 Redis。PostgreSQL/pgvector、CodeQL、模型服务和隔离验证运行时仍按所选阶段提供。

`app/services/stage_lifecycle.py` 统一阶段创建、审计就绪条件、目标归属、修复目标确认、
测试集覆盖和规则 holdout 适用性。`stage_actions.py` 负责明确的批准、取消、失联回收与新建重试。
人工判断写入 `candidate_decisions.py`，模型支持意见不转为人工确认。
HTTP 路由和 CLI 只转换输入、调用这些用例并呈现结果。

`app/cli/` 是执行适配器；`benchmarks/configs/cli/` 保存可版本化配置。
数据集抽样、隐藏答案、独立评分和论文统计继续留在 `benchmarks/`，不进入模型执行状态。
第一版支持单样本、多样本顺序执行和重复实验，不提供 TUI 或新的评分实现。

## 运行环境

复用仓库根目录的 `.env` 或环境变量。最少需要 `PROJECT_NAME`、`DATABASE_URL`；模型阶段还需要
既有 AI 配置。密钥只放环境配置，实验 JSON 不接受密钥字段。
先安装锁定依赖并对实验专用数据库执行迁移，避免把正式实验混入产品数据库：

```sh
cd system
uv sync --locked --package app
cd backend
../.venv/bin/alembic upgrade head
cd ..
```

`run`/`batch` 会初始化 LangGraph 的 PostgreSQL 检查点表，不替代 Alembic 业务迁移。
查询包、CodeQL 路径和验证镜像沿用现有配置；知识库采集/索引仍使用
`scripts/seed_knowledge.py` 等已有入口。ZIP 保留产品提取限制，不以 CLI 绕过文件数或体积门槛。

控制台入口安装后为 `semflow`。也可以从 `system/` 使用已有解释器运行，无须重新构建包：

```sh
PYTHONPATH=backend .venv/bin/python -m app.cli --help
PYTHONPATH=backend .venv/bin/python -m app.cli validate \
  --config ../benchmarks/configs/cli/scan-review.example.json
```

`--help` 和 `validate` 不连接数据库、不导入 Web 或任务队列。
`validate` 只检查配置结构；不会启动扫描，也不宣称归属、环境和工具已通过运行检查。

## 配置与调用

示例是 [scan-review.example.json](../benchmarks/configs/cli/scan-review.example.json)。
将实验 ZIP 放到仓库忽略的 `artifacts/inputs/sample.zip`，或复制配置并修改路径。
`archive` 相对配置文件解析，支持 Python 或 JavaScript。`dual_engine: false` 只运行静态扫描；
开启双引擎会额外运行产品内的初审模型分支，其策略仍沿用产品配置，需要单独记录和核对。
`stages: []` 可用于纯静态基线。

```sh
semflow run --config plan.json --sample sample-001
semflow batch --config plan.json
semflow inspect --run-id <experiment-or-audit-or-stage-id>
semflow inspect --run-id <stage-id> --evidence --logs
```

`repetitions` 控制整批重复次数；每个样本每轮创建新的实验执行 ID，新的扫描拥有新的审计 ID。
样本也可以指定 `audit_id` 复用当前工作区已有审计，但必须省略 `archive`，并至少请求一个阶段。
复用时不重新扫描，也不复制审计历史。每个后续阶段仍获得独立的 StageRun。

阶段支持 `scout`、`review`、`repair`、`rule`、`report`、`verification_suite` 和 `verification`。
`inputs` 使用已有阶段契约；`verification` 只接受 `repair_id` 和 `suite_id`，身份由服务重新派生。
修复不会自动选择或确认本轮新候选；先检查证据并确认，再用审计 ID 和候选 ID 发起修复。
报告输入由实际审计记录生成，不接受外部传入的结论。

模型阶段的 `budget` 支持 `max_calls`、`max_tokens`、`max_seconds` 和可选 `model`，三项上限必须为正数。
CLI 创建的这些阶段采用 bounded 策略，冻结 Prompt 内容、版本和校验值；模型适配器仍执行既有
阶段专用约束，因此实际限制可能更严格。静态工具超时仍由 `SCAN_TIMEOUT` 等适配器配置控制。

规则消融可以显式设置 `rule_experiment`，例如：

```json
{
  "retrieval_mode": "bm25",
  "collection_routing": false,
  "full_feedback": false
}
```

这些开关映射到已有规则实现，不创建新的方法分支。还支持语料 document ID 白名单、
生成约束、语义反馈、上下文压缩、源码准备上下文和检索时机。
省略字段保留已有阶段版本行为。`vector`/`hybrid` 仍要求相应索引和嵌入配置。

## 人工确认与执行恢复

```sh
semflow decide --candidate-id <candidate-id> --status confirmed \
  --evidence-id <evidence-id> --reason '已核对当前快照中输入到危险操作的路径与防护条件'
semflow resume --run-id <rule-stage-id> --reason '已逐行核对正负样本与预期告警位置'
semflow cancel --run-id <stage-id>
semflow recover --run-id <stale-stage-id>
semflow retry --run-id <failed-or-cancelled-stage-id>
```

`decide` 对确认/排除要求属于当前源码快照的真实证据，保留人工决策历史。
`resume` 专用于规则正负样本人工批准，从该阶段的持久化中断检查点继续，不重新生成规则。
它不会自动运行原实验中尚未执行的下游阶段；后续用同一审计 ID 创建新配置。
原实验收据保留当时的等待状态，`inspect` 的 `current_stages` 给出阶段最新状态。

`retry` 仅接受失败或已取消阶段，创建新 ID 并保留原 Prompt、模型策略，调用用量从新执行开始。
`recover` 仅回收超过 45 分钟无更新的运行阶段；不会自动重放可能已发生的外部调用。
Ctrl-C 保存实验中断状态和已登记的任务 ID，运行中阶段仍需先检查，再按现有回收机制处理。
取消在业务边界生效，当前外部命令可能仍需结束。本版这些动作作用于阶段，不处理扫描重试。

## 产物和实验口径

每次样本执行在 `ARTIFACT_ROOT/runs/<experiment-id>/` 保存：

| 文件 | 内容 |
|---|---|
| `experiment-input.json` | 独占创建的输入配置、样本与重复编号、工作区、实现指纹 |
| `execution-events.jsonl` | 追加式任务登记、阶段结束、中断及最终状态事件 |
| `execution-receipt.json` | 原子更新的执行收据，引用实际 AuditRun、StageRun 与产物目录 |

实现指纹包括 Git 提交、脏工作区标记、已跟踪差异摘要、后端 Python/Prompt 文件哈希及关键依赖版本。
指纹不备份工作区，也不证明第三方模型可确定性复现；正式实验应冻结干净提交、锁文件、
查询包/镜像和数据快照。扫描版本及源码哈希沿用 AuditRun，模型配置与用量沿用 StageRun。
耗时是本次样本的墙钟时间，复用审计时不包含历史扫描时间；模型用量保留分阶段结构，不伪造费用。

stdout 为 JSON，进度和诊断走 stderr，可直接重定向导出。批量执行按顺序处理样本，
单样本失败不吞掉其他样本，也不自动重试。收据明确记录未执行的阶段数量；
`completed` 只表示流程完成，不等于发现已人工确认、规则有效或补丁通过独立 oracle。
聚合评分时必须保留失败、取消、中断和未评估样本，不能把它们当成功的零发现结果。

| 退出码 | 含义 |
|---|---|
| 0 | 请求完成；inspect 可查看失败记录但自身查询成功 |
| 1 | 执行结果中有失败、取消、阻塞或其他未完成状态 |
| 2 | 配置、操作前提或数据库访问错误 |
| 3 | 无失败，但有阶段等待人工确认 |
| 130 | 用户中断 |

旧 `scripts/benchmarks/formal_runtime.py` 已复用共享阶段执行生命周期。
显式传入的历史研究子图仍保留原选择；仅接受单参数的生成子图没有检查点续接能力，
不会把其输出冒充完整产品规则验收。旧冻结实现及既有结果不因这次抽离而变更。
