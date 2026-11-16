# 三内核双入口：最终操作验收清单

DEC-ACC-000 | 2026-11-13T11:36:00+08:00 | completed

本项仅表示清单已制定；下列实际运行尚未执行。执行人：主会话；独立复核：监督会话。用户已确认验收现有命令式 CLI，**不新增 TUI**。

## 1. 唯一交付目标与停止条件

三个实验 core（双引擎发现、native/OpenHands 修复、RAG QL 生成）与平台分离。CLI 直接调用 core；Web 通过桥接调用同一 core。相同科研输入、选项、结果、状态及必要产物具有一致语义，两边均能正常完成现有流程。平台拥有任务编排、展示和人工确认/接受/发布。

本轮只验收并修复阻断上述目标的问题。不做算法改进、抽象美化、全目录整理、清空 legacy、batch/消融、全面 CI、全量 BenchmarkPython、正式实例部署。独立安装与已有 Docker 启动方式的可用性属于交付检查，不扩展为发行平台建设。只使用合成小样本、隔离实例和既有工具资源。

完成条件：下面 ACC-001～009 有逐项证据且无必需路径阻断；ACC-010 给出独立结论。外部资源缺失记 blocked，不把 skip/mock 当实际运行通过。发现问题只修对应入口/转换/契约，然后复跑受影响项；无变更且已通过的无关检查不重复跑。成功后结束本轮，不自动进入后置维护。

## 2. 执行顺序与账本

| 稳定 ID | 北京时间 | 状态 | 本项交付与通过条件 |
| --- | --- | --- | --- |
| DEC-ACC-001 | 2026-11-13T18:12:59+08:00 | completed | 固定迁移前/当前代码、样本、工具、参数与证据目录；确认三条静态问题的处置 |
| DEC-ACC-002 | 2026-11-13T16:25:59+08:00 | completed | 平台隔离启动：数据库迁移、API、worker、beat、真实 GUI，以及现有 Dockerfile 构建路径 |
| DEC-ACC-003 | 2026-11-13T16:25:59+08:00 | in_progress | 仓库外独立安装 CLI，四切片命令实际运行，无 backend/DB/Redis/Web 依赖 |
| DEC-ACC-004 | 2026-11-13T18:12:59+08:00 | completed | GUI 实际完成发现、两种修复、规则批准/恢复/验收流程；截图与端到端关联齐全 |
| DEC-ACC-005 | 2026-11-13T18:12:59+08:00 | completed | 同一方法参数下，CLI 与 GUI 的 core 请求/结果/必要产物语义对照通过 |
| DEC-ACC-006 | 2026-11-13T18:12:59+08:00 | completed | 迁移前归档与迁移后实现的固定小样本兼容对照，差异逐项解释 |
| DEC-ACC-007 | 2026-11-13T18:12:59+08:00 | blocked | 少量失败/取消/批准恢复检查；正常/失败/未评估不混淆 |
| DEC-ACC-008 | 2026-11-13T18:12:59+08:00 | completed | 三个 core 的有界真实模型连通冒烟，与确定性对照分别报告 |
| DEC-ACC-009 | 2026-11-13T18:12:59+08:00 | completed | 证据清点、仅停止本轮资源、精确列出残留与阻断；实际实例不变 |
| DEC-ACC-010 | 2026-11-13T18:12:59+08:00 | planned | 监督会话复核运行证据和验收前后代码 diff，作最终通过/不通过判断 |

所有项状态使用 planned/in_progress/blocked/completed，变更时更新时间。运行明细另记 outcome=pass/fail/blocked，避免把“检查做完”写成“功能通过”。每项至少记录命令、退出码、代码摘要、样本 ID、execution/stage ID、证据相对路径及替身范围。

## 3. 冻结输入与处理已知阻断（ACC-001）

1. 阅读[静态代码复核](backend-decoupling-code-review-20261113.md)。先最小复现 REV-001（独立 discovery 的 lock 路径）、REV-002（Docker workspace 缺失）、REV-003（rule-validate 文档顺序）。修复只限可用性及对应回归，不重构算法。固定“验收前”和修复后的源码摘要，保留 diff。
2. 当前基线必须包含未跟踪的 contracts/research/research_cli/research_bridge、新迁移与 Prompt。不能只用 Git HEAD 或 git diff。只读复制到专用验收目录，排除 .git、.env、真实上传与历史产物；依赖环境单独准备。前端构建会写 backend/app/frontend，必须在副本进行。
3. 迁移前使用 `artifacts/decoupling/baselines/20261110T152154-ebb9cb83/implementation.tar.gz`，SHA-256 必须为 `2241989b58b3889a12a3b221fb141d6b9e3d3ac9af7b5569f72c0facb2dde01e`。其 HEAD 是 `0a9bd9ae493b24a4189deabe08b25fb1bb8ee05c`；归档包含当时脏工作区，不可仅拿该 HEAD 代替。17:54 的归档已经处于迁移中，不是 before。
4. 在独立目录用旧 HEAD 的归档补足结构，再覆盖上述已核验归档；不 checkout/reset 当前工作区。逐项标出补足文件来源。旧归档不含前端源码，旧 GUI 若无法精确恢复，必须披露“前后后端行为对照，当前 GUI 实测”，不能声称原 GUI 完整重现。旧/新依赖不同则各用各自锁定环境并记录。
5. 创建 `artifacts/decoupling/acceptance-<北京时间>-<短ID>/`，子目录建议 `inputs/ before/ after-cli/ after-web/ compare/ logs/ screenshots/ diffs/`。保存源代码清单与 hash、源码 zip 与解压树、options/resources 非秘密内容、Prompt、查询包、语料、suite/holdout 的摘要。
6. secrets 只通过显式环境变量注入；不复制/打印主项目 .env。保存命令时不含 key。运行记录注明真实与替身模型/工具。GUI 截图、HAR/trace 中也不得泄露凭据。

固定样本集合只用一个合成 Python 项目：复用 `artifacts/decoupling/real-web-native-full-2c-20261112-v3/35e88596-68b5-4507-bedb-3ad09f499033/research/workspaces/35e88596-68b5-4507-bedb-3ad09f499033/source/app.py`。该 source 目录只有 app.py；配套测试复用现有小型 suite/测试夹具，不假定源码目录已有测试。冻结本轮完整树及 hash，不把旧 patched-source 当原始源。必要正/负 fixture 和独立 holdout 另冻结，各一组，必须与开发样例不同。固定两个检索文档集合（reference、rule_example），使用现有小型真实 CodeQL 材料，不收集大语料。

| 样本用例 | 固定运行范围 | 核心断言 |
| --- | --- | --- |
| M1 发现 | 同一源码，scan/scout/review/discover 各入口一次 | 危险 eval 有真实位置证据；安全位置不被该查询命中；scout 不读取静态结论；未复核保留未评估 |
| M2 native | M1 的一个人工确认目标，最多一个可写文件 | patch/Diff 可查看；syntax、project_tests、rescan、suite 前后验证按选项实际执行；原源码不变 |
| M3 OpenHands | 同一目标/源码，单文件范围和固定 worker/image | 真正启动固定 SDK/容器，补丁与检查收据完整，不能偷偷转 native |
| M4 RAG rules | 一个需求、固定语料、正/负 fixture、一个独立 holdout | 检索→生成→编译/开发检验→项目重放→批准/恢复→独立检验；QL 与批准主体不变 |

每个切片每个入口只需一次正常运行；既有结果可供 inspect/replay，不重跑模型。M1 独立子入口可用定向小测试补足，避免每次重新扫整个集合。不扩语言/漏洞类型矩阵。项目重放须显式打开；旧真实规则样本 `scope.json` 中 project_replay_requested=false，不能直接据此宣称项目重放验收通过。

## 4. 实际启动隔离平台（ACC-002）

执行人先选空闲端口并记录。示例约定：数据库 25440，Redis 26380，API 28001，GUI 25174。冲突时换端口，不停止已有进程。以下变量由执行人设置为本轮绝对路径：`DEC_TREE`=当前代码副本，`DEC_RUN`=产物目录，`DEC_ENV`=本轮权限 0600 的 shell 环境文件，`DEC_PROJECT`=唯一 Compose project 名；文件不进入 Git。

环境至少显式覆盖 `POSTGRES_PASSWORD`、`UI_DB_PORT`、`UI_REDIS_PORT`、`DATABASE_URL`（本轮 audit 数据库）、`REDIS_URL`（本轮 Redis）、`ARTIFACT_ROOT=$DEC_RUN/platform-artifacts`、`PROJECT_NAME`、`FRONTEND_HOST`。资源显式指定 CODEQL_BIN/PYTHON_BIN/PACK_PATH、查询包版本、验证镜像、OPENHANDS_PYTHON/IMAGE、模型 endpoint/profile 与预算。默认读取仓库 .env 的 Settings 不应把本轮导向正式服务；副本不带该文件，关键路径必须启动前核对。

以下为操作模板，后续执行时记录实际路径/端口和命令，**不是本清单已经执行的记录**：

```sh
# 每个终端均加载本轮文件；文件内仅使用合法 shell 赋值，路径正确引用。
set -a
. "$DEC_ENV"
set +a
cd "$DEC_TREE/system"
docker compose --project-name "$DEC_PROJECT" --env-file "$DEC_ENV" -f compose.yml up -d db redis
# 等待本轮 db/redis 健康，核对容器及映射端口，随后在 backend/ 执行：
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.initial_data
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 28001
```

其他独立终端（同一环境，均在副本）分别启动：

```sh
# cwd=$DEC_TREE/system/backend，记录进程 PID、工作目录及日志
../.venv/bin/celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
../.venv/bin/celery -A app.jobs.celery_app:celery_app beat --schedule "$DEC_RUN/celerybeat" --loglevel=INFO
# cwd=$DEC_TREE/system，前端代理必须与实际 API 端口相同
SEMFLOW_API_PROXY=http://127.0.0.1:28001 npm run dev --prefix frontend -- --host 127.0.0.1 --port 25174 --strictPort
```

准备依赖用现有锁文件；只在副本创建环境，资源缺失先记录，不自动升级版本。`/api/v1/utils/health-check/` 返回 true；前端页面实际可访问；数据库迁移处于 head；worker ready 且能接收真实队列任务。核对当前初始数据/本地工作区的实际页面，不凭旧说明虚构登录步骤。

另在副本 system/ 执行已有 `docker build -f backend/Dockerfile -t semflow-decoupling-acceptance:<run-id> .`，记录构建日志与 image ID。REV-002 未修前应先记录构建错误；不以宿主机可启动抵消容器交付缺陷。不要求把完整 CodeQL runner 改造为容器平台。镜像/网络缺失记外部 blocked。

当前 Vite 默认 5174/API 8001，旧 README 的 5173/8000 不可混用。`npm run lint` 带 --write，不能当只读检查运行；本轮无需全仓自动格式化。

## 5. 真实 CLI 与 GUI 操作（ACC-003/004）

### CLI：无平台运行

在全新虚拟环境安装本轮三个 wheel 及锁定依赖；工作目录位于仓库外，不设源码 PYTHONPATH，不复制 backend，不用 system-site-packages。可复用 `verify_research_install.py` 做安装预检，但必须继续运行业务命令。进程不提供 DATABASE_URL/REDIS_URL/平台配置，不调用平台 API；endpoint 仅指向显式模型服务。保留 PTY/终端 stdout、stderr、退出码，命令不得依赖测试 monkeypatch 启动器。

由现有 public Options/ResourceFile 类型准备少量 options/resources JSON；提供方法参数、源码/上游结果、可写范围和资源即可。禁止为通过验收而要求用户手填一套执行 UUID、内容摘要或自编 Python 业务胶水。

```sh
semflow-research discovery-discover --root "$DEC_CLI_ROOT" --source-directory "$DEC_SOURCE" --options "$DEC_INPUT/discover.json" --resources "$DEC_INPUT/resources.json"
semflow-research discovery-scan --root "$DEC_CLI_ROOT" --source-directory "$DEC_SOURCE" --options "$DEC_INPUT/scan.json" --resources "$DEC_INPUT/resources.json"
semflow-research discovery-scout --root "$DEC_CLI_ROOT" --source-directory "$DEC_SOURCE" --options "$DEC_INPUT/scout.json" --resources "$DEC_INPUT/resources.json"
semflow-research discovery-review --root "$DEC_CLI_ROOT" --upstream-execution-id "$DEC_DISCOVERY_ID" --options "$DEC_INPUT/review.json" --resources "$DEC_INPUT/resources.json"
semflow-research repair-native --root "$DEC_CLI_ROOT" --upstream-execution-id "$DEC_DISCOVERY_ID" --candidate-id "$DEC_CANDIDATE_ID" --writable app.py --max-changed-files 1 --options "$DEC_INPUT/native.json" --resources "$DEC_INPUT/resources.json" --dependency-lock "$DEC_INPUT/uv.lock" --confirm --actor acceptance-operator --reason '已核对固定源码和证据'
semflow-research repair-openhands --root "$DEC_CLI_ROOT" --upstream-execution-id "$DEC_DISCOVERY_ID" --candidate-id "$DEC_CANDIDATE_ID" --writable app.py --max-changed-files 1 --options "$DEC_INPUT/openhands.json" --resources "$DEC_INPUT/resources.json" --dependency-lock "$DEC_INPUT/uv.lock" --confirm --actor acceptance-operator --reason '已核对固定源码和证据'
semflow-research rule-generate --root "$DEC_CLI_ROOT" --upstream-execution-id "$DEC_DISCOVERY_ID" --candidate-id "$DEC_CANDIDATE_ID" --confirm --actor acceptance-operator --reason '已核对规则目标与源码证据' --documents "$DEC_INPUT/documents.json" --options "$DEC_INPUT/rules.json" --resources "$DEC_INPUT/resources.json" --dependency-lock "$DEC_INPUT/uv.lock"
semflow-research inspect --root "$DEC_CLI_ROOT" --execution-id "$DEC_RULE_ID"
semflow-research decide --root "$DEC_CLI_ROOT" --execution-id "$DEC_RULE_ID" --actor acceptance-operator --reason '已核对冻结 QL 和正反例'
semflow-research rule-validate --root "$DEC_CLI_ROOT" --decision-file "$DEC_DECISION_FILE" --resources "$DEC_INPUT/resources.json"
semflow-research resume --root "$DEC_CLI_ROOT" --decision-file "$DEC_DECISION_FILE" --resources "$DEC_INPUT/resources.json"
```

ID 从实际命令结果读取，不能预造成功收据。规则当前 `rule-validate` 只能在仍等待批准时执行，因此暂按 decide→rule-validate→resume；REV-003 必须明确解决文档契约，不得默默绕过它。若修复改为允许完成后复核，补执行文档承诺的 resume→rule-validate 顺序。等待批准退出码 3 是预期暂停，不是失败；批准主体须实际查看。

native 的 build_suite/verify 目前交付说明使用 `run --spec`。本轮必须核实普通用户完成完整修复所需的 suite/verify 输入可从现有入口/产物获得；记录实际准备步骤。若必需步骤只能靠平台 DB、手写复杂底层协议或测试辅助函数才能完成，列为极简 CLI 可用性缺口，不能用高级入口理论可调用替代。仅在此阻断确实存在时补最小装配入口，不造新命令框架。

### GUI：真实浏览器、真实队列

不得用 TestClient、直接调用 run_stage、page.route 伪造业务 API 代替以下操作。使用浏览器/Playwright 指向本轮 URL，保留截图及 trace（脱敏）。现有 mock 前端测试可作补充，不计本项证据。

1. 打开首页/工作区，上传固定源码 zip；实际观察扫描排队、worker 执行和完成。打开静态发现、源码位置与证据，记录 audit ID、scan execution ID。
2. 从现有页面启动双引擎发现；查看两个分支及统一复核。分别检查普通 scout/review 现有入口可用；结果有覆盖范围，partial/未评估不显示成已排除。
3. 对一个候选在 UI 明确人工确认，再启动 native 修复。保留正常前端 `rescan:true` 等选项；查看 attempts、原/补丁源码、Diff、syntax/project_tests/rescan 结果；生成/选择现有 suite，完成 before/after 比较和自动后续任务。修复之前不能显示 accepted；满足检查后由 UI 人工接受。
4. 同一原始快照启动 OpenHands 分支；核实真实 worker/SDK/镜像身份及单文件范围；展示 Diff 和检查结果。它可以与 native 产生不同补丁，不要求两个不同算法字节一致。
5. 从规则页面选择固定语料/目标与参数，生成规则；查看检索来源、QL、编译/开发 fixtures 和项目 replay。看到等待确认后，实际审阅并批准 fixtures；等待原执行恢复。检查独立 holdout 收据，再进行现有 confirm-project-match 和 publish 人工流程。技术通过不会自动发布；无 holdout 分支必须维持 draft/not_evaluated 并拒绝发布。
6. 刷新页面并重启本轮 worker，重新打开结果、Diff 和规则材料；不重跑模型即可查看已发布的 core 产物。记录平台 StageRun→ResearchBinding→core execution→manifest 映射，证实未走 legacy 当前算法。

## 6. 两种“一致性”分别验收（ACC-005/006）

**A：新 CLI vs 新 GUI。** 对同一切片锁定相同源码字节、显式方法版本、Prompt 内容、模型策略、范围、预算、工具链、语料/检索参数、验证开关和人工决定。CLI scout 默认 8、平台有版本 7 路径，不能各跑默认然后声称同一方法。先比较进入 core 的冻结请求；请求不等价则先修/解释入口映射，不比较输出碰运气。

**B：迁移前 vs 迁移后。** 在各自隔离环境运行旧归档实际算法和新 core，使用相同外部模型响应脚本/录制响应与真实小型工具。不能用当前 legacy 文件冒充归档，也不能拿新 Web 与新 CLI 的互相比对当作 before/after。仅在模型边界提供固定响应，禁止替换研究图、桥接、CodeQL/SARIF、补丁或投影。脚本应按阶段/输入断言匹配，不能无条件回放成功；输入上下文差异须报告。

最小结果比较表：

| 层 | 必须比较 | 允许差异及处理 |
| --- | --- | --- |
| 请求 | operation、method/prompt、源码树、范围/目标/决策、预算、检索/验证开关 | 执行 UUID、平台 actor 表示、存储根可映射；不得漏字段或改默认值 |
| 发现 | rule/file/range、证据字节、model_assessment、评估覆盖、候选来源 | ID 依据证据/来源建立显式映射；不能把未评估与排除归一化 |
| 修复 | patch 字节、改后源码树、attempt、检查种类/状态、before/after、原源码不变 | 同一算法+固定模型响应应一致；容器绝对路径可转相对路径 |
| 规则 | 检索文档及顺序、QL/modules/dependencies、fixtures、replay、holdout、批准主体 | fixture 测试运行时间可不同；不能忽略查询/证据/hash 不同 |
| 状态 | completed/failed/cancelled/awaiting_input、错误类别、partial/not_evaluated | 平台展示状态单独列映射；技术检查不等于人工接受/发布 |

UUID、时间、耗时等逐字段白名单归一化，保存原始 JSON 和映射文件。源 hash 旧/新算法不同，应从相同文件字节分别计算验证，不删除 hash 字段来“达成一致”。model_assessment 与人工决定分离是已明确的边界变化，单列预期差异；不拿旧自动 confirmed 充当新人工确认。科学内容或算法顺序出现新差异必须解释或修复，不要求无关展示 DTO 字节相等。

只需一个短比较脚本/报告，不开发通用 diff/回放平台。固定响应不证明模型效果；实际模型不保证输出逐字一致，分别使用下面的冒烟判据。

## 7. 少量异常与真实模型（ACC-007/008）

既有回归可选下列五个节点作一次前置烟测（在副本 system/、本轮隔离数据库环境下执行）；有参数化时记录实际用例数。它们主要验证边界/流程，仍含替身，不抵消上述业务命令与真实 GUI 的要求。仅修复导致其他路径变化时扩展定向测试：

```sh
.venv/bin/python -m pytest \
  tests/test_research_discovery_bridge.py::test_web_scout_and_direct_sdk_share_the_same_kernel_and_api \
  tests/test_research_repair_workflow.py::test_existing_web_suite_rescan_followup_and_human_acceptance \
  tests/test_research_openhands_process.py::test_web_and_cli_same_openhands_process_contract \
  tests/test_research_rule_dual_entry.py::test_frozen_rule_request_has_same_web_and_fresh_cli_meaning \
  research_cli/tests/test_independence.py::test_platform_bridge_imports_only_public_kernel_interfaces \
  -q --junitxml="$DEC_RUN/targeted-smoke.xml"
```

- 一个扫描/解析失败：明确工具失败/损坏 SARIF，不是成功零发现；CLI 非零、GUI 错误与 core 失败一致。
- 一个运行中取消：终端/GUI 请求取消后实际停止，状态/用量保留；重复投递不重新生成。复用现有取消集成测试加一条现场路径，不做全模块故障矩阵。
- 一次规则进程退出后批准恢复：新进程/新 worker 消费同一 checkpoint；生成调用数不增加，QL/modules/fixtures hash 不变；篡改一个批准主体被拒绝；另复用无 holdout 测试证明 draft/not_evaluated。
- 四切片各一次有界真实模型正常冒烟，可直接与 ACC-003/004 同次执行合并；模型/endpoint 固定，记录真实调用和预算，失败保留，不自动多次换 Prompt 直到通过。不在本轮测漏洞准确率、修复成功率、规则泛化率。
- 若先用脚本模型跑确定性 GUI，再跑真实模型，分别标记；真实模型资源不可用时写明哪些连通验收 blocked，不能把脚本响应写作真实模型。外部资源问题不直接推断为解耦失败，但未完成项目不得标 pass。

## 8. 收尾交接与最终判断（ACC-009/010）

主会话交付一张 pass/fail/blocked 表、完整实际命令、原始/归一化请求结果、旧新差异表、浏览器截图/trace、worker/core 关联、错误/取消记录、资源身份、前后源码清单及最小修复 diff。历史 JUnit 可复用，但修改路径需定向复验；总测试数不作为目标。

只停止本轮登记的 PID 与 Compose project；若需清理，精确指定本轮容器/临时卷，不执行全局 prune，不删除验收证据。正式平台的数据库/队列/服务/源码产物不被改动。

监督会话复核：修复是否只解决真实阻断；当前两个入口是否仍进同一 public/core；输入开关、失败状态、证据和人工门是否保持；是否新增绕过检查的测试特例；before/after 差异是否有依据。最终分别给出“代码边界目标”“独立 CLI 实用性”“完整 GUI 实用性”“迁移前后兼容”四项结论，均通过才宣布本次操作验收完成。

交给主会话的执行指令：**按本清单依次执行，先最小复现/修复三个静态问题，再隔离启动并完成固定小样本。不得开启新架构阶段。每完成一项更新状态及证据路径，全部运行完成后交由监督会话审查 diff；不以原 S6 completed 或 mock 测试数替代现场验收。**

## 本轮执行位置

运行 ID：`20261113T133759-26ecb8`；记录于 `artifacts/decoupling/acceptance-20261113T133759-26ecb8/`。当前源码副本在 `/private/tmp/semflow-acceptance-20261113T133759-26ecb8/tree`，不包含主 .env、真实上传和产物；验收前归档含 1275 文件，SHA-256 `4ca2178adf85cb940658aeb4b877d4a0b072f6c715a023769be0804955d0ee1c`。旧归档 SHA-256 已验证匹配清单要求。

### 2026-11-13T16:25:59+08:00 操作证据

ACC-002：隔离 Compose DB/Redis、迁移、API/worker/beat/GUI 均已实际启动；修复后 Docker 构建退出 0（修复前退出 1）。日志与镜像摘要见本轮 `operational-progress.json`、`logs/docker-build-after.log`。未迁移或重启实际平台。

ACC-003/004 仍进行中：仓库外 after wheel 安装退出 0；实际 discovery-scan 退出 0，execution `7f881cbc-ba0c-43c9-a20c-38a96e086db7`。GUI 实际上传后经 HTTP/Celery 完成 CodeQL 与独立 scout，静态告警和假设均定位 app.py:5；复核已通过按钮提交。仅模型边界为确定性 HTTP 替身，不代表真实模型验收。REV-001/003 定向回归 15 passed；规则待批准现场流程尚未执行，不提前关闭该项。

### 2026-11-13T17:38:26+08:00 现场新增发现（仍非最终验收）

| 稳定 ID | 北京时间 | 状态 | 证据与处置 |
| --- | --- | --- | --- |
| DEC-ACC-FIX-004 | 2026-11-13T17:38:26+08:00 | in_progress | 日常 CLI 缺少 build_suite/verify，新增 public 机械装配与两条薄命令；同时增加按 suite execution 和上游真实 scan 选择输入，避免手写 ArtifactRef。新进程/独立性 11 passed，后续受影响最小 CLI 14 passed；仓库外真实工具验收仍进行中。 |
| DEC-ACC-FIX-005 | 2026-11-13T17:38:26+08:00 | completed | GUI 原先仅发送默认 native，增加显式引擎选择并在 DTO 两端注释禁止静默降级；真实 SDK 1.56.0/容器通过 GUI 队列生成 OpenHands 补丁，真实前后测试通过并人工接受。首次替身 HTTP 协议失败保留为独立失败执行。 |
| DEC-ACC-FIX-006 | 2026-11-13T17:38:26+08:00 | in_progress | discover→review 错把索引协调器当叶生产者，新增新进程回归先复现后修复；增加 run_review=false 对齐 Web 的分步流程。复核后 rescan/replay 基线选择缺口也已修复，从冻结输入保留原基线；不读 live 默认或工作目录。复扫现场待复验。 |
| DEC-ACC-FIX-007 | 2026-11-13T17:38:26+08:00 | in_progress | GUI 把 needs_review 零告警结论写成“仍有告警”，改为“复扫结论仍需人工复核”；语义状态和验收门不变。等待隔离页面复验。 |

GUI native：真实语法、复扫（AI 来源仍需复核）、测试集生成、两轮前后断言、Diff 与人工接受均已执行。OpenHands：真实 SDK 沙箱读源/补丁/finish，随后真实检查与自动平台前后验证、人工接受。截图位于本轮 screenshots/，绑定与原始请求保存在 after-web/platform-before-rule-approval.json。

规则：实际编译/开发正反例/原项目重放后等待批准；只重启登记 worker，再由 GUI 批准恢复，独立测试通过。查询与正反例未重新生成（恢复前 generation HTTP 调用数 1，恢复后需最终核对）。本样本由内置 CodeQL 已覆盖，当前规则是明确 baseline_reuse；不存在可如实填写的“原基线不属同根目标”依据，保留不可发布状态，不编造排除依据，不改发布门。四份官方局部语料已实际编译并冻结；首轮缺少 CWE/中文主题匹配保留失败历史，补充真实别名后新执行通过。

CLI 首轮受网络沙箱阻断，静态成功但模型分支 provider_error，不能计为完整通过；已保留部分收据并以本地 HTTP 必需权限新建执行。v3 双引擎 scan/scout 实际成功；未复核候选仍明确 partial，独立 review 后 full。仓库外 daily repair 等路径仍在继续。

### 2026-11-13T18:12:59+08:00 最终现场结果与监督交接

| 稳定 ID | 状态 | outcome | 事实依据 |
| --- | --- | --- | --- |
| DEC-ACC-001 | completed | pass | 本轮 1275 文件当前源码归档、迁移前归档 SHA、固定样本、依赖和修复 diff 已冻结。 |
| DEC-ACC-002 | completed | pass | 隔离 DB/Redis、迁移、API、worker、beat、前端及 Docker 修复构建实际完成；只清理本轮登记资源。 |
| DEC-ACC-003 | completed | pass | after-v4 wheel 在仓库外安装；discovery、repair-native、suite、verify、OpenHands、rule-generate/decide/validate/resume/inspect 命令均已执行。首轮本地网络沙箱失败单独保留。 |
| DEC-ACC-004 | completed | bounded-pass | GUI 实际完成发现、统一复核、人工确认、native/OpenHands 修复、真实 Docker 检查、两轮前后断言、Diff 和人工接受；规则检索/生成/编译/开发正反例/项目重放/批准恢复完成。规则发布因样本与原基线同根，缺少真实排除依据而被正确阻断，未伪造发布。 |
| DEC-ACC-005 | completed | pass | `compare/cli-web-semantic.json`：53/55 原始比较相等；两处 readable scope 是契约声明的等价编码，未解释差异为 0；补丁、after tree、检查、QL、依赖、fixtures、检索内容和控制开关均相等。 |
| DEC-ACC-006 | completed | bounded-pass | 旧 HEAD + SHA 核验迁移前归档在独立 audit_before 库实际运行旧 CLI discovery/native/suite/verify；旧归档不含前端，未声称历史 GUI 重现。wheel AST 对比显示无非 public 算法或 Prompt 变化。 |
| DEC-ACC-007 | blocked | incomplete | 终端取消拒绝和失败/批准恢复均有证据；GUI 取消按钮操作时任务已结束，未形成运行中取消收据，不能声称通过。 |
| DEC-ACC-008 | completed | partial-fail | 用户指定真实 `deepseek-v4.1-flash`：discovery scout 1 次真实调用成功（5867/5103 tokens，36.8s）；native repair 2 次后因阶段预算不足失败；RAG rules 2 次因 APITimeout 失败。三内核连通性已真实触达，算法质量不作结论。 |
| DEC-ACC-009 | completed | pass | `final-operational-report.json`、CLI/Web 对照、旧归档、截图、真实模型收据、cleanup 记录齐全；正式平台未迁移/重启/写入。 |
| DEC-ACC-010 | planned | pending supervisor review | 监督会话需要复核本轮证据、修复 diff、失败边界和上述 blocked/partial 结论。 |

本轮最终证据入口：`artifacts/decoupling/acceptance-20261113T133759-26ecb8/final-operational-report.json`。真实模型凭据没有写入 JSON、日志、截图或 Git；临时私有文件已删除。

### 2026-11-13T18:25:31+08:00 realvuln 真实项目联通测试

选用 `realvuln-Damn-Vulnerable-Flask-Application`，固定 commit `55f63201c85190e760a8fa34a580a9bf918dbf36`，归档 SHA `c174277b2b5245be5fca410eefb11322ca126b81f732d2049a4b706110375333`。真实 CodeQL 扫描完成并命中 `app.py:120` 的 `py/code-injection`，与该项目 ground truth 的 eval/CWE-94/95 条目同位置。真实模型 scout 完成一次调用但结果为 partial（项目仍有未检查范围）；真实模型 review 完成一次调用并返回 supported，证据引用 `app.py:120`。这只是一个真实项目的运行联通和证据链测试，不是 RealVuln 全量评分。首次 scout 因测试输入 resource profile 不匹配被拒绝，已记录为输入契约问题并在测试输入中修正，没有改代码。

真实项目证据：`after-cli/realvuln-scan.json`、`after-cli/realvuln-scan-summary.json`、`after-cli/realvuln-scout-real-v2.json`、`after-cli/realvuln-review-real.json`、`after-cli/realvuln-real-project-summary.json`。
