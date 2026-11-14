# 独立科研 CLI

`semflow-research-cli` 只导入 contracts 和 research public，不导入 app、平台桥接或平台配置，不读平台 `.env`、不创建平台实体、不调用 Web API。

```sh
semflow-research capabilities
semflow-research schema --kind run
semflow-research schema --kind result
semflow-research schema --kind event
semflow-research validate --spec run-spec.json
semflow-research capture-source --directory /absolute/source --root /absolute/research-root --owner-execution-id <uuid> --language python
semflow-research run --spec run-spec.json --resources resources.json --root /absolute/research-root
semflow-research inspect --root /absolute/research-root --execution-id <uuid>
semflow-research cancel --root /absolute/research-root --command-file cancel-command.json
semflow-research cancel --root /absolute/research-root --execution-id <uuid>
semflow-research rule-generate --root /absolute/research-root --source-directory /absolute/source \
  --documents corpus-documents.json --options rule-options.json --resources resources.json \
  --dependency-lock /absolute/uv.lock
semflow-research decide --root /absolute/research-root --execution-id <uuid> \
  --actor experiment-operator --reason '已核对正反例和冻结查询'
semflow-research rule-validate --root /absolute/research-root \
  --decision-file /absolute/research-root/decisions/<uuid>/<command>.json --resources resources.json
semflow-research resume --root /absolute/research-root \
  --decision-file /absolute/research-root/decisions/<uuid>/<command>.json --resources resources.json
semflow-research discovery-scan --root /absolute/research-root --source-directory /absolute/source \
  --options discovery-options.json --resources resources.json --dependency-lock /absolute/uv.lock
semflow-research discovery-scout --root /absolute/research-root --source-directory /absolute/source \
  --options discovery-options.json --resources resources.json --dependency-lock /absolute/uv.lock
semflow-research discovery-discover --root /absolute/research-root --source-directory /absolute/source \
  --options discovery-options.json --resources resources.json --dependency-lock /absolute/uv.lock
semflow-research discovery-review --root /absolute/research-root --upstream-execution-id <execution-id> \
  --options discovery-options.json --resources resources.json --dependency-lock /absolute/uv.lock
```

run 已直达已交付 discovery 的 scan / scout / review / discover；日常最小入口另提供 `discovery-scan`/`discovery-scout`/`discovery-review`/`discovery-discover`，均直接调用同一 public core。日常测试集与前后验证使用 `repair-build-suite` / `repair-verify`，由已发布 execution 自动取得不可变引用；run 仍可执行 native / OpenHands repair generate、build_suite / verify 和 method 8 rules generate。规则可返回 typed 等待批准结果；`rule-generate`/`decide`/`resume` 可独立完成有或无 holdout 的批准恢复；`rule-validate` 从批准生成清单建立独立技术复核执行，不重新生成。继续沿用 `public.runs.resume` 的原检查点。CLI 的 retry / batch 仍是后置实验管理功能；capabilities 已将四个必需 discovery 操作、repair 操作和 rules generate/validate 列入 implemented。旧 `semflow` 是历史平台兼容入口。统一交付和后置清单见[交付摘要](../../design/development/backend-decoupling-delivery-20261113.md)；implemented 表示双端边界验收，experimental 仅列未验收入口，当前为空。

`rule-options.json` 只包含科研参数（需求、用途、策略、模型/预算、检索、生成、开发开关和批准计划），不要求填写执行 ID、Prompt 引用或工具链摘要；`corpus-documents.json` 是显式冻结的 reference/rule_example 文档数组。缺少 holdout 时恢复结果仍是 `draft`/`not_evaluated`，不会获得发布资格。`rule-generate` 资源文件通过模型 endpoint profile 装配 CodeQL 资源和模型 URL；凭据仍不写入 JSON。

native / OpenHands 日常入口从上游发现结果选目标，不需要手写 RunSpec、执行 ID、摘要、Prompt 或 Python 胶水：

```sh
semflow-research repair-openhands \
  --root /absolute/research-root \
  --upstream-execution-id <discovery-execution-uuid> --candidate-id <candidate-uuid> \
  --writable app.py --max-changed-files 1 \
  --options openhands-options.json --resources resources.json --dependency-lock /absolute/uv.lock \
  --confirm --actor experiment-operator --reason '已核对该候选对应的冻结源码和证据'
```

native 使用相同参数调用 `repair-native`，options 类型为 `public.repair_requests.RepairOptions`，省略 OpenHands 专有的 `worker` 字段；两条命令复用同一个装配函数，分别直达同一 repair public 的引擎分支。

`--candidate-id`、`--writable` 和 `--readable` 可重复。未指定 readable 时只允许读取 writable 文件；目录 readable 授权覆盖其子路径。`--confirm` 是本地操作者对选定候选及原证据的明确确认，不能从模型意见推断；它不接受生成的补丁。准备后 stderr 给出执行 ID，可用另一终端 inspect/cancel；最终结果仍从 stdout 输出。

`openhands-options.json` 类型为 `public.repair_requests.OpenHandsOptions`，只包含科研参数：`model`、`policy`、`worker:OpenHandsPolicy`、`method_policy`、`validation_plan`，以及可选 `suite` 和 `method_version`（默认 4）。这些对象与 RunSpec 中相同，CLI 不替换其默认值或验证开关。日常可设置 `rescan_from_upstream=true`，直接沿用上游发现的真实基线和原扫描参数；可用 `suite_execution_id` 选择已发布测试集，无需手写 suite 引用。两者不能与对应的显式引用混用。可用 `schema --kind openhands_policy` 查看 worker 声明，完整参数见 `schema --kind run`；`schema --kind openhands_receipt` 导出收据。高级 `run --spec` 保留。

资源文件的类型声明在 `semflow_research.public.configuration.ResourceFile`：`profile_id` 必须对应冻结请求的 `policy.resource_profile`；`settings` 经 ToolSettings 严格校验；`model_endpoints` 分别按 `model.endpoint_profile` 和 `worker.endpoint_profile` 选择 `base_url / api_key_env`。OpenHands 需配置 `OPENHANDS_PYTHON`（SDK 1.56.0 的解释器）与 `OPENHANDS_IMAGE`（必须等于 worker 的 sha256 镜像身份），默认使用研究包中的 worker。凭据只从显式环境变量引用解析，不写 RunSpec 或资源快照。同一执行不能更换非秘密资源或 worker 字节；变更方法或工具需新执行。

validate 只校验结构，返回 `scope=contract_structure_only`，不创建执行。capture-source 捕获显式指定目录的完整字节，不将它用作平台配置来源。inspect 核验已发布清单与产物；没有结果时返回 null。cancel 的 JSON 是版本绑定的 ControlCommand，仅记录请求，实际停止由执行器在安全边界声明。

`rule-validate` 是对仍处于 awaiting_input 的冻结生成产物的独立复核；合法顺序是 `rule-generate → decide → rule-validate（可选）→ resume`。同一决定在 resume 完成后不能再用于这个待批准复核入口；需要新复核时应创建显式的新执行。

正常结果走 stdout JSON；输入 / 资源错误走 stderr，退出码 2；执行失败 1、等待输入 3、已取消 130、中断 4。help 使用 argparse 输出。规则批准续接通过 `decide` 写入精确 ControlCommand，再由 `resume` 在新进程消费；`rule-validate` 可从批准生成清单创建独立技术复核执行。CLI 不伪造批准，也不把技术复核升级为平台发布。

从 `system/` 运行源码检查：

```sh
PYTHONPATH=contracts/src:research/src:research_cli/src .venv/bin/python -m semflow_cli capabilities
.venv/bin/pytest contracts/tests research/tests research_cli/tests -q
uv lock --check --offline
```

严格 wheel 安装检查：

```sh
.venv/bin/python scripts/verify_research_install.py \
  --wheels ../artifacts/decoupling/wheels \
  --environment ../artifacts/decoupling/new-isolated-check
```

检查器使用空虚拟环境和三个 wheel，对完整运行依赖闭包核对 uv.lock 条件分支、版本与 RECORD 字节，拒绝平台包和 system-site-packages。v7 已验证 63 个锁定运行依赖；此前 anyio 报错来自校验脚本忽略 resolution-markers，已修复，无需变更锁定版本。新源码打包后需生成新的验证报告，不复用旧五个 Pydantic 依赖报告。完整门见[DEC-009](../../design/development/backend-decoupling-todo-20261110.md)。

### 测试集生成与前后验证的最小命令

```sh
semflow-research repair-build-suite --root ./research \
  --upstream-execution-id "$DISCOVERY_ID" --candidate-id "$CANDIDATE_ID" \
  --confirm --actor experiment-operator --reason "已核对该候选的冻结源码和证据" \
  --requirements-file ./requested-behavior.txt --options ./suite-options.json \
  --resources ./resources.json --dependency-lock ./uv.lock
semflow-research repair-verify --root ./research \
  --repair-execution-id "$REPAIR_ID" --suite-execution-id "$SUITE_ID" \
  --options ./verify-options.json --resources ./resources.json --dependency-lock ./uv.lock
```

`suite-options.json` 包含 `model` 与 `policy`，使用已有冻结 Prompt 方法 2。`verify-options.json` 包含 `policy` 和独立的 `syntax`、`project_tests`、`rescan` 布尔选择（默认 false），固定执行同一组断言的两轮修复前后比较。`rescan=true` 要求原修复已经冻结真实基线；不会使用当前默认查询替代。验证引用直接取已发布 repair/suite，不需要手写 ArtifactRef、hash 或平台 ID。测试通过不等于接受补丁。

`discovery-discover` 的 options 可显式指定 `run_review=false`，只运行双引擎，再通过 `discovery-review --upstream-execution-id ...` 复核组合结果。省略时仍保留原本的组合复核行为。复核发送的是经过验证的叶集合生产者身份，并保留真实静态基线。
