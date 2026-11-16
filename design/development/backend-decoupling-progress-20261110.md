## 当前交付状态（S6 | 2026-11-13T11:22:31+08:00 | completed）

S1～S5 限定交付 completed：discovery 四操作、native/OpenHands repair、method 8 RAG rules 均经 CLI/Web 调用相同 public core。S6 已完成能力输出、状态/文档和后置分流的收口，未变更算法。

- capabilities：implemented 与 experimental 不重叠；明确 implemented_engines=native/openhands、implemented_methods=8；完成范围为 core_cli_web_boundaries，不声明模型效果或实际部署。
- TODO：DEC-001/004/005/006/007/009/012 按已接受交付范围关闭；原任务状态/正文保留为历史，DEC-010/013 仍 planned。后置项分列 DEC-POST-001～004，均未执行。
- 边界：复用独立进程 import guard、public-only 静态检查和 wire/Schema 注释检查；新增 bridge 禁止直接模型/CodeQL/图调用检查。
- 工作区：已有改动归属混合/未知，未 reset/提交、覆盖 AGENTS.md 或变更 benchmark。S6 前状态和选定文件摘要保存在忽略目录 `artifacts/decoupling/s6-status-20261113/before.json`；历史收据不重算。

- 本轮验证：能力/独立导入/bridge 边界与 wire Schema 检查 **23 passed**，报告 `artifacts/decoupling/s6-boundary-check-20261113.xml`；未重跑 S5 全矩阵或真实工具。轻量检查约束直接导入和执行，不能替代后续算法语义审查。

S6 completed。后置任务保持 planned；到此停止主动扩展。

入口、契约与后置项见[交付摘要](backend-decoupling-delivery-20261113.md)，原 S5 验收见[矩阵](backend-decoupling-s5-matrix-20261113.md)。

<details>
<summary>S1～S5 与早期迁移记录（历史原文；当时的未完成项不代表当前缺口）</summary>

## S5 总验收与收口（S5 | 2026-11-13T18:05:00+08:00 | completed）

- 规则产品入口缺口已闭合：`tests/test_research_rule_bridge.py::test_existing_project_match_route_is_the_platform_validation_acceptance_gate` 证明现有 Web `approve-fixtures → resume → confirm-project-match → publish` 路径等价覆盖 `rules.validate` 产品语义。科研验证仍由 core 执行，平台只做人工作品匹配、权限和发布事务。
- 固定总矩阵：discovery、native repair、OpenHands repair、RAG rules 各有 core/CLI/Web/契约/失败恢复记录；最小矩阵 **64 passed / 2 skipped**，JUnit `artifacts/decoupling/s5-total-matrix-20261113-v2.xml`。Native/OpenHands 均有同一冻结请求的 CLI/Web 对照。
- 独立性/契约检查继续通过：独立回归 **166 passed / 3 skipped**，Ruff 和 `git diff --check` 通过；没有新增 AGENTS.md 规则、协议框架、wheel/CI 或 benchmark 范围。

S5 必需范围已完成。旧未绑定执行继续由 legacy executor 负责，新四切片入口均走 research public；DEC-006 的历史清理、DEC-012 实际实例部署、批量/效果评测等后置事项不阻塞本次解耦交付。

## S4 发现四操作双入口验收（S4 | 2026-11-13T16:20:00+08:00 | completed）

- Core：`semflow_research.public.discovery` 已实际执行 `scan`、`scout`、`review`、`discover`；双引擎静态扫描与独立 Scout 使用分离 execution/record/artifact 命名空间，Scout 不读取静态结果；review 只接收显式冻结 bundle，未复核候选和失败分支保留。正常 `discover` 已移除“未接通”路径。
- CLI：新增 `discovery-scan`、`discovery-scout`、`discovery-review`、`discovery-discover`，自动装配源码快照、CodeQL pack/suite、Prompt、执行策略和 upstream bundle。新进程禁止导入 app/FastAPI/Celery/SQLModel/pydantic-settings，重复 inspect/cancel 语义通过。
- Web：现有上传扫描、双引擎扫描、普通 Scout、统一 review 均继续通过 `research_bridge` 调用同一 public core；平台只冻结源码、规则、候选/证据 bundle 和身份映射。静态 SARIF 失败、Scout 模型失败、review 不足覆盖、取消、重复投递和投影恢复均有证据。
- 契约：复用 run/result/bundle/evidence/event 与现有 wire 注释；保留 StaticBaseline、SARIF raw ID、Candidate/Evidence/coverage/derived_from、失败和 partial 语义。未知模型判断不会写成人工 confirmed。
- 回归：core/CLI/Web discovery 专项 **35 passed**，JUnit `artifacts/decoupling/s4-discovery-regression-20261113.xml`；Ruff lint/format 通过。

S4 已完成其限定范围。DEC-006 的历史算法清理和更广泛失败矩阵仍按原 TODO 保持进行中；整体仍未完成，下一阶段是 S5 总矩阵，不在本阶段顺手清理 legacy。

## S3 规则双入口小样本收口（S3 | 2026-11-13T17:10:00+08:00 | completed）

- Core / CLI / Web：`rules.validate` 与 `rule-validate` 已接通；验证新执行只接收已批准生成 manifest，不读生成 workspace，不重新生成 QL。未选 holdout 仍 `not_evaluated`/draft；正反例失败保留 `failed` receipt。
- CLI/Web 对照：同一冻结 method-8 请求经平台 worker 与平台无关的新 CLI 进程进入同一 public core，查询、依赖、fixtures、retrieval、project replay 状态和 usage 语义一致；平台根因确认仍由 Web 保留。
- 平台保护：查询、模块、依赖、样例、最新人工确认或 stage 输入变化均拒绝批准；投影中断后可从科学清单恢复，不再生成；SARIF opaque finding ID 与平台 UUID 的边界已写在发送/接收注释。
- 回归：合同/研究/CLI、规则 bridge、双入口和保护专项 **172 passed / 3 skipped**，JUnit `artifacts/decoupling/s3-rules-regression-20261112-v2.xml`；Ruff 通过。
- 真实小样本：CodeQL **2.23.5**、显式 Python 3.11、固定 `codeql/python-queries@1.6.0`，method 8 生成/编译/正反例/独立 holdout 通过 **1 passed**；证据 `artifacts/decoupling/real-rule-cli-20261112-s3-v2/ce8bb8eb-e21c-4916-9152-732838dcce40/`。模型和操作者是脚本/替身，未评估模型质量，未扩大 benchmark。上一轮 Python 3.15 抽取失败已保留为失败产物。

S3 已完成限定验收：现有 `confirm-project-match`/发布路径被证明是平台人工作品匹配与发布入口，科研验证由 `approve-fixtures → resume` 的同一 public core 完成；S4 发现四操作已完成，S5 总矩阵仍待完成。

## S3 RAG 规则双入口续接（S3 | 2026-11-12T18:35:00+08:00 | in_progress）

- Core：新增独立 `rules.validate` public 执行，读取已批准生成执行的 immutable manifest/query/modules/dependencies/fixtures、原 toolchain、holdout 与 project-replay 选择，在新 execution 中只运行验证，不重新生成；删除生成 workspace 后仍可完成，失败正反例保留为 `failed`/draft。未选 holdout 仍为 `not_evaluated`/draft。
- CLI：新增 `rule-validate --decision-file --resources`；`rule-generate`、`decide`、`resume`、`inspect` 在禁止平台导入的新进程中通过。批准、拒绝、过期 subject/凭据缺失、终态重复投递均有回归。
- 输入：新增部分向量冻结装配，保留未索引 chunk 并绑定完整 vector matrix digest；public/workspace 同名当前语料按 provenance scope 分开。
- Web：现有 method 8 binding 继续调用同一 `research.public.rules`，正常生成/项目重放/批准恢复/投影/发布回归为 3 passed；平台人工确认与发布仍由 bridge 持有。
- 当前专项（当时）：规则 core/CLI/语料/独立 validate **29 passed**，Web bridge **3 passed**；后续收口结果见顶部。

## S1 native 极简 CLI 补齐（S1 | 2026-11-12T15:47:30+08:00 | completed）

`repair-native` 复用已有 repair 本地装配：从上游发现结果、明确候选确认、文件范围、科研 options/resources 自动组装 native RepairSpec；不增加算法或 CLI 框架。`test_native_minimal_cli.py` 在禁止平台导入的新进程通过直接命令生成、inspect、参数/原源码/补丁对照与终态 cancel 拒绝门。与极简 OpenHands 和导入隔离专项合计 **12 passed**，Ruff 通过。旧 `test_repair_cli_pipeline.py` 仍只代表高级 `run --spec` 三进程链路，不能替代本次极简入口证据。此前关于 S1 的矛盾以此修正；现在进入 S3，整体解耦继续进行。

## S2 OpenHands 双入口验收（S2 | 2026-11-12T15:27:00+08:00 | completed）

OpenHands 继续复用原语义图和固定 SDK worker，两个入口均调用 research public。修复了冻结输入字段与 worker 名称不一致、实时读取 Prompt、硬编码总时限和遗漏外部模型预算等缺口；工作区只授权所声明的可读/可写范围，补丁再次核对已观察窗口与文件数。SDK 调用逐次持久预留并按实际已知结果结算；未知结果不重放。取消停止本次进程组并清理专属容器，不改原始源码。

- CLI：新增 `repair-openhands`，输入为上游发现结果、候选、明确确认、方法 options 与 resources；本地完成机械协议装配。新进程禁止导入 app/FastAPI/Celery/SQLModel/pydantic-settings，完成 run/inspect/cancel。高级 `run --spec` 保留。
- Web：新的 OpenHands 绑定调用相同实现，资源缺失明确失败。API 的 suite 生成/导入、默认 rescan、独立前后比较、Diff 与人工接受链路均覆盖 OpenHands；终态重复投递不启动 worker。
- 契约：`OpenHandsPolicy` 与 `OpenHandsReceipt` 有各自 Schema 和收发端注释；资源快照绑定实际 worker 字节。日志、事件、runtime、调用收据与部分 workspace 通过不可变 refs 保存，失败和取消也保留；删除可变目录仍可 inspect，篡改成员被拒绝。历史 usage-only 引用不升级语义。未新增 AGENTS.md 规则。
- 回归：S2 原有 **208 passed / 6 skipped**；JUnit 为 `artifacts/decoupling/s2-openhands-regression-20261112-final.xml`。S3 过渡回归另为 **152 passed / 3 skipped**，JUnit `artifacts/decoupling/s3-rules-progress-20261112-final.xml`；包含 S2 相关边界、规则 core draft/holdout、最小 CLI 和 Web bridge failure gate。Ruff lint/format 通过。
- 真实技术门额外 **2 passed**：实际 SDK 1.56.0、禁网 Docker 及语法检查；Web 与独立 CLI 对同一冻结请求得到相同补丁、状态、检查和用量。镜像 `sha256:d08218bf3488b62251326fed15e8170cfaf5ac6c329c2d02864e673c92aa7920`。core 执行 `b29f3ce9-6b7f-4ac2-ac69-9c7cc842feb4`；Web `406347f7-8318-4b03-aa53-12dda58ee613`、CLI `ab8030db-5a12-42a5-86ee-8abec68aecf2`。完整证据：`artifacts/decoupling/real-openhands-sdk-20261112-s2-v3/`。模型和操作者为明确替身，只用一个合成文件，不涉及效果评测或真实平台部署。

S2 按上述实际边界证据关闭。规则、发现最终对照、native 极简 CLI 的证据补齐与总体入口归一仍待后续；整体解耦尚未完成。下方保留纠偏和历史记录，不能把历史缺口或过度声明当作当前验收结论。

## S3 RAG 规则双入口开始（历史记录 | 2026-11-12T17:30:00+08:00）

- Core：修正未选独立 holdout 的语义；`RuleResult.independent_validation` 为 `not_evaluated` 时保持 draft。独立样例只在批准恢复后执行，项目重放要求 StaticBaseline；编译、开发、重放、holdout receipts 分开。
- 输入：平台 rule bridge 一次性冻结当前语料版本、完整连续 chunk、验证 provenance、可选向量矩阵、CodeQL toolchain 和 Prompt；research 检索只读 CorpusSnapshot/KnowledgeChunk scientific records。
- CLI：`rule-generate` 从源码目录、文档 JSON、options/resources 和 lock 装配请求；`decide` 生成 revision/checkpoint/subject 绑定的 ApprovalDecision 并调用 public resume。`research/tests/test_rule_minimal_cli.py` 覆盖无 holdout 的生成→等待→批准→恢复→draft。
- Web：`rule` stage 建立 binding，桥接冻结目标、语料、工具链与请求，调用相同 `research.public.rules`；资源/语料缺失返回 failed 和 diagnostics，不静默调用旧 RuleService。当前专项 `test_research_rule_bridge.py` 验证失败语义和无 legacy fallback；正常 Web 成功、完整 RuleVersion 投影、approve 路由恢复、项目重放/发布及 CLI/Web 同输入对照仍待补齐。
- 契约：新增 `RuleDiagnostics`、独立检验字段和 `rule_diagnostics` wire meaning；发送/接收端注释与 Schema 同步，无 AGENTS.md 变更。

S3 仍未完成，不能把 CLI draft 流程或 bridge failure gate 当作规则正常路径验收。

## S2 OpenHands 双入口进度纠正（2026-11-12T15:00:00+08:00 | in_progress）

S2 尚未完成结束条件。OpenHands 已接入 `research.public.repair.execute` 的装配和替身测试；真实 worker 字段转换、冻结 Prompt、范围/预算和失败产物仍有缺口，极简 CLI 与同输入 CLI/Web 对照也未完成。历史未绑定任务继续 legacy。下述 43 项仅为局部回归，不构成 S2 验收。

- Core：复用已提取 LangGraph/OpenHands worker，已声明 OpenHandsPolicy；字段到 worker 的映射及限额执行尚需验证，当前 usage 引用不等于完整 worker 收据。
- CLI：在不导入 app/FastAPI/Celery/SQLModel 的环境跑通 `run`、`inspect`，取消命令继续复用同一 control contract；脚本模型只替代外部模型/worker boundary，真实 public graph、账本、产物和状态保留。
- Web：`engine=openhands` 创建 research binding，冻结 OpenHandsPolicy，调用同一 public core，保留旧 Diff/materials/validation/人工接受边界；资源缺失明确失败，绝不降级 native。
- 契约：新增 `OpenHandsPolicy` 和 `AttemptRecord.engine_receipt`；wire meaning/Schema 连接尚缺，最新 wire 检查因此失败。此前 S2 局部专项 **43 passed**，不能替代此失败或完整边界验收。

S2 证据由明确的 OpenHands worker 替身和现有隔离边界测试组成；未把替身效果当作真实模型质量。OpenHands SDK/镜像实际执行仍需部署环境提供冻结资源，资源缺失路径已有直接失败门。规则、发现双端对照和总验收继续后置。

## S1 复核与真实技术门补充（2026-11-12T11:44:06+08:00）

- 当前科研/桥接回归：**175 passed / 2 skipped**；Ruff lint/format 通过。额外 CLI 三进程 `build_suite → generate → verify`、Web 生成/导入 suite、rescan、before-after、接受、失败/取消/恢复专项均通过。
- 固定合成 Flask 样本的完整真实 Web 门 **1 passed**：CodeQL 基线实际命中第 5 行；native patch 后真实 CodeQL 复扫清空；真实禁网只读 Docker pytest 镜像重复执行安全/功能断言；平台投影和人工接受成功。模型和操作者是显式替身。证据：`artifacts/decoupling/real-web-native-full-2c-20261112-v3/`，固定工具镜像 digest `sha256:d08218bf3488b62251326fed15e8170cfaf5ac6c329c2d02864e673c92aa7920`。
- 另一次 PostgreSQL 一次性兼容回归此前已 **53 passed / 2 deselected**，迁移 upgrade/check 通过后容器已删除；随后对已删除端口重跑旧选择只产生连接拒绝，不能计入新结果。
- 旧入口/历史执行器仍保留；规则平台独立 validate API 和总验收仍未完成。S4 发现双端对照已在顶部完成；DEC-007、DEC-015 保持 in_progress。
- v13 独立 wheel 安装验证已通过，继续保持无平台包和 RECORD 校验；S1 新增 suite/compare/contracts 仍在同一独立包边界内。

## S1 native 修复收口记录（2026-11-12T11:40:59+08:00）

S1 的 native 修复正常路径已贯通 core、CLI、Web 和契约：前端原样 `rescan:true` 请求、可选验证集、项目测试开关、suite 生成/导入、修复生成、原始 StaticBaseline 复扫、独立 before/after、StageFollowup、旧列表/Diff/materials/validation DTO 和人工接受均进入同一 research public core。平台仅冻结输入、映射身份、投影状态和执行接受事务；技术通过不会自动接受。

- CLI 在平台导入禁止时通过高级 `run --spec` 完成 `build_suite → generate → verify` 三个独立进程，使用冻结输入/脚本模型，验证无 backend/FastAPI/Celery/SQLModel/pydantic-settings 导入。证据：`research/tests/test_repair_cli_pipeline.py`。该测试不证明 native 极简输入装配已完成；S2 的极简命令仅覆盖 OpenHands，native 此项仍需后续补齐。
- Web 集成覆盖生成/导入 suite、rescan 清空/仍命中/工具失败/SARIF 失败/无静态关联、项目测试独立开关、断言失败/工具失败/取消、权限/篡改、重复投递、follow-up 发布失败、投影故障恢复和接受门。证据：`tests/test_research_repair_workflow.py`、`tests/test_research_verification_failures.py`。
- 固定一个合成 Flask 样本使用真实 CodeQL 和真实禁网只读 Docker pytest 镜像完成完整 Web 技术门：真实漏洞基线第 5 行，补丁后复扫清空，重复 before/after 安全断言由 assertion_failed→passed、功能断言保持 passed，人工接受完成。模型和操作者为明确替身；报告：`artifacts/decoupling/real-web-native-full-2c-20261112-v3/`。先前入口配置错误的失败收据保留在 `real-web-native-full-2c-20261112/failure-01-image-entrypoint/`，未覆盖失败结论。
- suite 运行器现在把原始 JUnit XML/控制台输出提交为不可变 ArtifactRef；删除运行目录仍可复核，篡改原始报告被拒绝。平台旧 hash/ID 与科研身份分开保存，静态复扫保留原始 SARIF/数据库/补充规则身份。

S1 仍不等于整体解耦完成：OpenHands core/CLI/Web、规则平台桥接与 validate/project replay/holdout、发现 CLI/Web 同输入对照和最终四模块总验收仍待后续阶段。DEC-007/DEC-015 保持 in_progress；本条只记录已验证的 native 范围。

## 阶段 2C 进行中（2026-11-12T09:50:55+08:00）

现有前端默认发送 rescan:true，2B 的 native syntax 切片原先会拒绝该正常请求；2B 不能称完整 Web 修复可用。本轮已接通无 suite 的默认复扫路径：冻结真实 StaticBaseline、查询包/补充规则与源码；科研内核复用原规则级前后判断，保留 checks 各自状态。补齐候选导入时丢失的 static_finding_id，显式映射旧/科研源 hash 所属告警身份。

5 项 API→worker→真实 bridge/native 图→技术适配器→投影→旧 API 集成通过（模型/扫描/容器为外部替身）：目标规则清空、仍命中、工具失败、SARIF 解析失败、无静态关联分别保留结论。失败不伪装零告警，原源码不变，重复投递不重跑。独立扫描/容器超时在协议中区分。suite build、before-after、project_tests、后续任务和人工接受的完整链仍在继续，尚未完成 2C。

## 阶段 2B：native 修复桥接实证（2026-11-11T23:27:53+08:00）

已用真实 `run_stage → repair_runtime → research native LangGraph → project_repair → RepairRecord / 旧 API` 贯通语法检查切片。该阶段的桥接验证已通过，DEC-007 仍为 in_progress，完整科研修复链路尚未完成。上一轮把冻结/分派测试描述为真实执行与恢复验证，证据不足；下面给出本轮实际结果。

- 修复输入使用独立 producer 和确定性候选/决策 UUID，通过 entity_map 回到平台 ID；验证最新人工确认、确认关联、证据字节/范围和原始源码，不能通过重新取证悄悄续期旧决策。
- 完整 ToolSettings 用 JSON 模式冻结，SecretStr 不持久化；首执行和恢复都仅注入当前凭据。保留 execution progress 模式的 None 总上限，分别传递初始/总取证、候选尝试与独立模型调用额度。run 语义修订 4。
- 实现/依赖摘要来自实际源码/uv.lock，不再接受占位值或绕过核验。新 OpenHands 请求明确拒绝，既有未绑定历史任务仍使用原执行器。
- 投影保留 failed / cancelled / interrupted、无结果失败/取消和不可变 manifest；保留原始命名检查、typed 收据、摘要与用量。终态重投不装配 provider/graph，删除工作目录和展示目录后可从 refs 恢复；已有人工接受记录不被覆盖。
- 科研收据与旧原生私有 hash 不混用。平台接受核验绑定、映射、检查收据、context/diff/修复副本，并保留旧历史分支；语法通过不能绕过前后验证和人工测试审阅。

验证范围：联合包/CLI/发现/修复桥接最终回归 **151 passed / 2 skipped**（两项真实 Docker 检查需 opt-in；本轮 Web/native 真实门另行运行通过）；修复桥接专项 17 项。投影故障注入位于文件已物化、数据库尚未提交处，恢复未重新生成。JUnit：`artifacts/decoupling/stage-2b-regression-20261111.xml`。一次性 PostgreSQL **53 passed / 2 deselected**，迁移 upgrade/check 通过，容器已删除。独立 wheel v12 仍是 63 个精确锁定依赖，严格离线安装/import/CLI 验证通过；Ruff 与 uv lock --check --offline 通过。

真实工具门额外 **1 passed**：Web/native 图使用现有固定镜像 `sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff` 检查一个合成文件，并投影/保存修复结果。execution `fd058f97-6007-427e-82a6-db73c6e05ba3`，input_digest `0d5b64b22534fad1753bb2730328c188921e0aab2285a4ccb99c6cbf95110596`。产物 `artifacts/decoupling/real-web-native-20261111/fd058f97-6007-427e-82a6-db73c6e05ba3`，模型/确认/上游扫描为显式替身；不是漏洞效果、完整方法或补丁接受验收。

剩余：suite build、before-after、rescan/baseline 和 OpenHands 完整科研公共路径与 Web 适配；规则平台桥接/独立验证、legacy 去重与整体切换仍按 TODO 继续。实际平台 DB 和运行实例未修改。

## 修复执行/投影继续（2026-11-11T16:40:00+08:00）

阶段 2B 正在纠正并验收 native repair 桥接。此前 134 passed / 1 skipped 仅覆盖输入冻结、分派替身和科研包回归，尚不足以证明 `run_stage → 真实 bridge → native graph → RepairRecord → 旧 API` 的完整执行、投影幂等或恢复；上一版把这些行为写为已验证，超出了测试证据。资源 JSON、安全注入、方法预算、人工确认与 ID 映射正在补齐，规则 Web 桥接继续后置。

suite、before-after、rescan、OpenHands、平台接受/发布和完整用户工作流仍未完成；历史未绑定 StageRun/checkpoint 保持 legacy executor。规则模块暂不推进。

## 修复纵向桥接开始（2026-11-11T16:05:00+08:00）

平台 native repair 新任务现在建立研究绑定，并将人工确认候选、真实源码证据、确认决策、PatchScope、方法 Prompt 和资源冻结为 RepairSpec；桥接拒绝 OpenHands，避免误切换旧执行器。冻结输入装配有合成边界回归。完整 native 结果投影、suite/before-after/rescan、OpenHands 和接受/发布工作流继续进行。

## 发现双入口纵向迁移（2026-11-11T15:28:07+08:00）

新扫描 / 双引擎、普通 Scout、统一复核 4～12 通过平台桥接调用科研 public，与独立 CLI 共用算法。平台新增执行绑定、类型化输入物化、投影及旧材料/SARIF 兼容视图；ID 与两种源摘要有明确转换，模型判断不代替人工确认。窗口补审适配与历史算法去重仍未完成。

最近联合回归 132 passed / 1 skipped；一次性 PostgreSQL 旧平台兼容回归 72 passed。两类绑定迁移 upgrade/check/downgrade/upgrade 通过，实际平台实例未迁移/重启。规则批准在新进程从原检查点续接的替身测试通过；完整修复、规则验证/平台桥接继续进行。

真实 CodeQL 再次用相同一个合成 Flask 样本验证，第 5 行命中、第 8 行无报告；科研数据库归档 583989 字节，导出兼容副本成功。产物：artifacts/decoupling/real-scan-baseline-20261111/；execution 9178fbc7-5221-4613-89b5-1901835e0e75。此为本地工具链可行性证据，不是模型效果或扩样实验。

后续以模块迁移为主线，通用实验运行基础设施增强后置。下面保留各阶段历史记录；历史“规则未接通 / anyio 阻塞 / 无 bridge”不再代表当前状态。

## 方向调整（2026-11-11T11:21:03+08:00）

以模块纵向迁移与 CLI/Web 共用科研内核为主线，发现优先；不再扩张通用科研运行基础设施。具体范围与历史验收见主 TODO 当前实施方向。v7 独立安装已通过；规则公共改动先完成回归，再推进平台发现桥接。旧记录、旧 checkpoint 和真实平台数据库均保留。

# 后端解耦实现与验证记录

范围：DEC-001～005 的首批实现；状态以[主 TODO](backend-decoupling-todo-20261110.md)为准。
这次交付通过了包与协议边界、真实本地存储和平台后续验证调度的机械验收，尚未完成三个算法内核迁移。

## 双引擎与 native 修复续接（2026-11-11T10:57:25+08:00）

- discover 通过三个计划子执行绑定编排 scan / scout / review，源分支并行但互不可读；只读索引保留原生产者和实体 ID。输入选择只导入选中记录，不能枚举同一生产者的其他状态或读取其可变工作目录。
- 复核候选显式 derived_from 原始候选；不在复核范围的候选保留原引用并标未复核。父子模型预算统一入账，子任务不能更换方法、Prompt、模型、策略或偷偷加入预算。
- native generate 接通冻结目标、操作者决策、范围、原生语义图和隔离副本。输出 RepairAttempts、每次上下文 / proposal / patch / patched_source / diagnosis / checks；公开内容摘要不替代原生图内部格式的 hash。
- syntax 与 project_tests 独立选择；禁用一致性时不调用该模型；没有选中检查时保留 needs_review。环境错误、检查失败、模型评价与补丁接受相互独立。
- 容器名从重复的 attempt-1 路径改为 execution + 唯一调用标识，超时只清理本次容器。并发隔离、产物篡改拒绝和删除工作目录后的不可变结果查询均有测试。
- CorpusManifest / CorpusCapture 固定两个集合、完整分块、来源 / 版本 / 验证信息及可选向量身份；同快照 ID 重复捕获幂等，内容变化冲突。检索使用真实 Haystack BM25，示例按全部分块重组；规则公共执行仍未接通。
- Model call 的 method_version 固定为算法版本，prompt_version 单独记录模板版本；独立版本回归验证二者不同也不会互相覆盖。

当前本地回归 **103 passed / 1 skipped**（Docker 需显式 opt-in），Ruff lint / format 通过。两条真实工具证据分别是：

| 工具检查 | 证据 | 限制 |
| --- | --- | --- |
| CodeQL 2.23.5，固定 python-queries 1.6.0 的 CodeInjection 单条查询 | 忽略目录 artifacts/decoupling/real-scan-20261111/；执行 1deff48b-0d4c-41fc-b43d-bef9fc18e62c；第 5 行命中，第 8 行无对应报告 | 一个合成 Flask 样本，不是方法效果评测或全量资源等价验收 |
| native 修复 + 真实 Docker 语法验证 | 额外 opt-in 1 passed；保存于 artifacts/decoupling/real-native-20261111/44047ea1-3246-42bc-bda2-613ee2ce32f9/ | 模型 / 操作者为显式替身，方法指纹为测试占位，不是生产或真实模型结论 |

Docker 使用本机已有 sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff（Python 3.11.15）；禁网、只读样本挂载、非 root、自动删除。没有构建 / 下载镜像或更改平台实例。

完整修复链路、规则生成 / 批准恢复、完整 CLI、bridge / 投影 / 引擎切换、真实模型 / 方法等价和完整锁定依赖安装仍未验收。Source code 指纹等声明尚需与安装实现做完整运行时绑定，不能把测试占位指纹当实际冻结证据。

## 当前续接实现（2026-11-10T19:58:49+08:00）

当前代码已超出首批包骨架；下方“首批”记录是历史快照，不能作为新增算法和依赖已验收的证据。

- 发现 `scan / scout / review` 已接到独立 public 入口，复用原算法和 LangGraph，未回调 app。双分支 discover、repair 和 rules 公共执行仍未接通。
- 独立科学记录采用显式 execution / upstream 范围、不可变输入与追加修订；嵌套写入由外层事务统一提交。修复读取 / 搜索 / 调用者枚举遵守同一冻结范围。
- 原生 LangGraph 容器以版本化 JSON + typed bytes 保存，绑定执行、输入摘要和固定引擎。真实新进程测试确认恢复不再执行生成节点；这不等于规则公共批准续接已经实现。
- 模型请求先持久预留预算，再调用服务；未知外部结果保留预留并拒绝自动重放。发现父子执行共享预算。接口结构校验和证据校验分开；每次调用的完整响应有内容引用。
- 源码快照使用规范 SourceManifest 摘要，拒绝重复、外来、缺失、篡改和符号链接条目；逻辑源码片段以 LF 连接且无末尾换行，原文件摘要仍针对原始字节。不能拿旧平台哈希直接替代。
- Candidate / Evidence / Assessment / Decision / StaticFinding 包有类型声明。原 SARIF ID 与协议 UUID 显式区分；复核保留静态生产者身份、原假设未知前提，模型评价不会写成人工确认。
- 工具资源序列化排除凭据，并落为内容引用；同一执行的工具路径、endpoint、镜像或预算变化会被拒绝，凭据可单独轮换。
- CLI 提供实验性 run、取消请求和源码捕获；资源文件只解析显式 endpoint profile / 凭据环境变量，不读平台配置。capabilities 的 fully accepted implemented 仍为空，experimental 明确列出三个发现切片。
- 12 类 JSON 边界通过 WIRE-SEND / WIRE-RECV 注释与 Schema 语义声明相连；要求 Agent 同改对端，约束没有新增到 AGENTS.md。

验证：本轮 contracts / research / research-cli 共 **81 passed**；Ruff lint / format、离线锁检查通过。调用模型 / CodeQL 的行为回归使用显式替身，真实 SQLite / 文件与跨进程 LangGraph 未替换。历史平台 66 项测试本轮未重跑。

独立 wheel 构建可用，但严格依赖安装未通过：anyio 的既有锁定版本是 4.15.1，本机安装 4.14.2 且本地缓存无锁定版本。校验器按完整运行依赖闭包检查版本与 RECORD，不使用 system-site-packages，不静默放宽锁文件。DEC-003 已重新标为 in_progress。未从网络下载依赖，未覆盖现有环境。

尚未验收：完整三内核、完整 CLI 控制流程、平台 bridge / 投影 / 引擎切换、真实模型与工具小样本。平台默认执行仍为 legacy；提取的未接通模块不能仅因 import 成功而视为完成。

## 首批实现（历史：2026-11-10T17:56:08+08:00）

## 已实现

1. 新增 `system/contracts`、`system/research`、`system/research_cli` 三个独立发行包，workspace 和锁文件已登记。
2. RunSpec 采用 module / operation 两层判别，覆盖发现 4、修复 3、规则 2 种操作；结果、事件、证据、批准、控制与验证收据使用独立类型。
3. 本地产物按执行隔离与哈希核验；只有显式引用的上游产物可读，路径和符号链接不能越出执行范围。
4. 本地 SQLite 账本实现独占领取、输入不可变、事件去重、结果版本比较、清单原子可见与崩溃回读。清单提交前失败不会生成成功记录。
5. 源码取证校验完整文件清单与实际片段，结构合法但伪造、跨快照或已经变更的证据会失败。
6. 科研 CLI 提供 validate / schema / capabilities / inspect；不导入平台框架，也不读取平台 `.env`。
7. 修复图移除了自动 enqueue；平台应用层接管后续验证，完成记录与 StageFollowup 意图同事务提交。
8. 增加后续任务租约、重复投递抑制、目标提交后丢指针恢复、任务繁忙延期、队列失败保留与 Worker 已领取状态保护。

## 验证证据

| 验证组 | 结果 | 范围 |
| --- | --- | --- |
| contracts / research / research-cli | 43 passed | 九种操作契约、未知字段 / 版本拒绝、真实证据、任务隔离、输入篡改、崩溃与事件去重、CLI 导入边界 |
| 修复 / 验证 / runtime / follow-up / stage API | 27 passed，2 deselected | 真实 PostgreSQL / pgvector；并发领取、重复投递、失效租约、提交后崩溃补偿、队列异常；明确排除 integration 验证器 |
| OpenHands / Repair3 / 报告 / 规则 / legacy CLI | 39 passed | 共用调度入口的回归，规则人工暂停恢复、报告与旧实验入口 |
| 独立 wheel 安装 | 通过 | 空虚拟环境无 app、FastAPI、Celery、SQLModel、pydantic-settings；导入三个 public API、导出 Schema 和校验结构 |
| Alembic | 通过 | 临时库全量 upgrade、check 无遗漏、新迁移 downgrade / upgrade 往返 |
| 锁与静态检查 | 通过 | `uv lock --check --offline`，Ruff lint / format，diff whitespace；既有第三方包版本未变 |

合计 109 项 pytest 用例通过。模型、CodeQL 和验证器使用所选测试的显式替身；这些数字不代表漏洞准确率或真实模型效果。
平台数据库测试使用新建、随机本地端口、临时内存卷的 `pgvector/pgvector:pg17` 容器；未连接现有平台数据库。

独立安装时，离线缓存缺少 Pydantic 索引元数据，因此从 wheel 安装三个本地包，
仅复用现有环境中与 uv.lock 版本一致、按安装 RECORD 校验过的五个 Pydantic 依赖。
没有使用 `--system-site-packages`，没有复制或安装平台包；未声称重新从包索引下载依赖。
复现工具是 `system/scripts/verify_research_install.py`，报告保存在忽略目录
`artifacts/decoupling/wheel-verification-v2-report.json`。

## 冻结与历史保留

| 快照 | 内容 | 忽略目录中的归档 SHA-256 |
| --- | --- | --- |
| `20261110T152154-ebb9cb83` | 改造前 549 个文件；当时已验证 14 项原生命周期基线 | `2241989b58b3889a12a3b221fb141d6b9e3d3ac9af7b5569f72c0facb2dde01e` |
| `20261110T175407-3572bae7` | 本轮 593 个代码 / Prompt / 测试 / 配置文件，包括三个新包 | `2e37f55273ca4ae923c6c7593ae9751935d9e88ff0d4fe5b3fc38e6b3868d202` |

两份清单和代码归档保存在 `artifacts/decoupling/baselines/<id>/`，没有覆盖历史快照。
归档不包含 `.env`、真实上传项目或审计产物；Git HEAD、脏工作区差异摘要和逐文件哈希均在清单中。
当前使用的是已有未提交工作区；没有重置、提交或合并用户的其他改动。

## 平台行为变化与部署前置

- 直接调用 legacy 修复图只完成修复并记录后续意图；它不再替调用方投递 Celery。平台 `run_stage` 正常触发应用层投递。
- `StageFollowup` 不是科研状态，也不向独立 CLI 暴露；它只负责平台运行实例的自动串联。
- 必须按既有部署流程应用迁移 `c1d202611100`，再启动更新后的 API / Worker；本次只对临时数据库执行迁移。
- 正常链路在运行结束后即时投递。进程崩溃后的 pending / 过期租约需要 Celery beat 或手动运行 `python -m app.application.repair_followups` 补偿。
- 队列投递不是恰好一次；重复消息由持久化领取抑制。已失败的比较任务保留历史，操作者仍需明确新建重试。

## 首批快照的未完成项（历史，以当前续接实现为准）

- 三个内核的算法、模型适配器、工具 / 检索资源装配尚未迁移；公共 execute 明确返回 unsupported_operation，capabilities 的 implemented 列表仍为空。
- 科研 CLI 尚无算法 run / batch / resume / retry / decide。旧 `semflow` 仍是依赖平台的 legacy 入口。
- 科研检查点、批准后续接、外部调用未知结果处理、完整模型用量账本仍属于 DEC-004。
- 平台 execution binding、实体映射、结果投影 inbox / outbox 尚未进入使用，属于 DEC-005 / DEC-011 的后续部分。
- CodeQL 包、镜像、语料与真实方法版本的完整冻结，以及三内核真实工具小样本验收仍待完成；未扩大 BenchmarkPython 样本。

下一阶段按 DEC-004 / DEC-006 先完成静态发现的独立执行切片，再迁入粗筛 / 复核、修复与规则生成。
未通过各自固定验收门前，平台不切换默认引擎，旧检查点和旧实验记录不改写。

</details>


## 2026-11-13T18:12:59+08:00 最终操作验收（DEC-ACC-001～009）

现场证据与边界见 `design/development/archive/20261116-document-consistency/backend-decoupling-acceptance-checklist-20261113.md` 和 `artifacts/decoupling/acceptance-20261113T133759-26ecb8/final-operational-report.json`。独立 CLI、真实 GUI、迁移前归档对照、CLI/Web 语义对照和用户指定真实模型连通性已执行。ACC-007 仍 blocked（没有形成运行中取消收据）；ACC-008 为 partial-fail（真实模型 discovery 成功，repair 因预算、rules 因超时）；ACC-010 保留 supervisor review。不能据此宣布全部操作验收完成，也不改写前三内核的科研结果语义。


## 2026-11-13T18:25:31+08:00 realvuln 现场联通

已选真实 Flask 项目 `realvuln-Damn-Vulnerable-Flask-Application`（固定 commit 与归档摘要见验收清单），执行真实 CodeQL、真实模型 scout 和 review。CodeQL 命中 ground truth 同位置 `app.py:120`；scout partial 保留未检查范围；review supported 且带源码证据。没有修改测试项目、算法或平台数据。
