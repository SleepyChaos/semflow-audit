# 后端解耦代码边界与迁移映射

当前实现、版本与交付范围见[交付摘要](backend-decoupling-delivery-20261113.md)及可执行 contracts Schema。本文保留初始提案；其中计划中的通用 retry、实验管理或逐文件清理不是当前能力声明。

<details>
<summary>2026-11-10 初始设计提案原文（历史）</summary>

# 后端解耦代码边界与迁移映射（待实施）

提案时间：2026-11-10T14:08:02+08:00。实施任务见[TODO](backend-decoupling-todo-20261110.md)，字段见[数据契约](backend-decoupling-contracts-20261110.md)。
路径均相对仓库根目录。下面为目标结构；已存在的包与待迁移目录以实现记录为准。
三个独立包及平台 application 的首批代码已建立，实际交付范围见[实现与验证记录](backend-decoupling-progress-20261110.md)；
下列逐文件迁移表仍是后续工作清单，并非已搬迁清单。

## 1. 包边界：科研 CLI 不属于平台

```text
system/
  contracts/                         # 独立发行包 semflow-contracts
    pyproject.toml
    src/semflow_contracts/
      common.py                      # ID、位置、ArtifactRef、错误与版本
      runs.py                        # RunSpec、ResultEnvelope、事件、控制命令
      discovery.py                   # 发现输入、候选、评估、覆盖
      repair.py                      # 目标、补丁、尝试、验证输入输出
      rules.py                       # 规则、语料、批准与检验
      validation.py                  # 共享验证收据；不实现检查
  research/                          # 独立发行包 semflow-research
    pyproject.toml
    src/semflow_research/
      public/                        # CLI / 平台可导入的稳定入口与能力查询
        discovery.py
        repair.py
        rules.py
        runs.py
      discovery/                     # 扫描、粗筛、统一复核、证据门与覆盖
      repair/                        # 语义取证、native / OpenHands、验证与诊断
      rules/                         # 检索编排、生成、开发反馈与技术检验
      evidence/                      # 只读取证、来源与真实引用校验
      runtime/                       # 执行上下文、账本、用量、控制、检查点适配
      ports/                         # Model、Scanner、Retriever、Verifier 等 Protocol
      adapters/                      # CodeQL / Docker / 模型 / 检索 / 本地存储
      prompts/                       # 包资源，按用途与版本保存
  research_cli/                      # 独立发行包 semflow-research-cli
    pyproject.toml
    src/semflow_cli/
      main.py                        # semflow-research，薄命令路由
      config.py                      # 科研配置解析与默认值完整展开
      sources.py                     # 导入目录 / ZIP / Git，冻结源码快照
      experiments.py                 # 样本 / 批次 / 重复 / 调用三个 public API
      actions.py                     # 本地决策、inspect / resume / retry / cancel
      output.py                      # JSON stdout、进度 stderr、退出码
  backend/app/                       # 平台发行包，仍为 Web 系统实例后端
    api/                             # HTTP 适配；不拼科学结果、不直接实现接受门
    jobs/                            # 领取 / 投递平台任务；不包含科研图
    application/                     # 上传、阶段、人工动作、接受 / 发布、后续调度
    research_bridge/                 # request_mapping / runner / projection_mapping
    presentation/                    # DTO、进度、中文解释、Diff / 报告视图
    persistence/                     # 平台 ORM、事务、绑定、inbox / outbox
    core/                            # 平台配置与装配，独立于科研 CLI 配置
    services/、runtime/               # 仅迁移期 facade / legacy executor
  scripts/benchmarks/                # 既有评测源码；新入口只用科研 public / CLI
  tests/                             # 先按职责分组，按需迁入各包 tests
  pyproject.toml、uv.lock             # workspace 与唯一锁；各包仍能独立安装
benchmarks/
  configs/research-cli/               # 新科研 CLI 配置，不含密钥 / oracle
  manifests/、prompts/、experiments/   # 既有科研协议、材料与实验历史
```

目标不是强制马上生成树中全部小文件；按职责迁移，手写文件通常 150–300 行，超过 400 行检查职责，超过 500 行拆分或说明。
`public` 承担稳定入口与参数类型，内部根据业务拆分；不把每个函数单独建文件。
`system/agents/openhands/` 保持独立运行工具 / 固定依赖，内核通过其 adapter 调用，不把 Agent 的依赖直接并入平台或 CLI。

## 2. 依赖方向与安装验收

| 包 / 层 | 允许依赖 | 禁止依赖 |
| --- | --- | --- |
| semflow_contracts | Python 标准库、固定 Pydantic 版本 | 其他业务包、ORM、Web、图框架、配置副作用 |
| semflow_research 三内核 | contracts、自身 evidence / ports / runtime、LangGraph | app、CLI、benchmarks、FastAPI、Celery、SQLModel、平台 User / Workspace |
| research adapters | contracts、内核端口、所需工具库 | app.core / app.persistence、平台知识 ORM、从目录反查平台 stage |
| semflow_cli | contracts、research.public、CLI 自身装配 / 本地源导入 | app.*、平台桥接、平台 .env、HTTP / Redis / 平台 DB 作为运行前提 |
| app.application | 平台 domain / persistence、research_bridge、contracts | research 的内部模块、CLI |
| app.research_bridge | contracts、research.public、平台 repository / resource provider | API 路由、jobs 具体任务、前端组件、内核内部 service |
| app.presentation | contracts、平台 query / DTO、授权产物读取器 | 算法执行、模型生成、科研结果回写 |
| app.api / jobs | 平台 application / presentation、输入 DTO | 算法细节、LLM Prompt、科研内部图 |
| benchmarks 新执行入口 | research.public 或独立 CLI、独立评价器 | app ORM / services / workflows，隐藏 oracle 进入 RunSpec |

research 包可选择安装 vector / postgres-checkpoint extras；默认本地 BM25 + SQLite / 文件执行账本不要求 PostgreSQL。
需要向量检索时显式配置独立只读检索资源或冻结索引，不把“连平台知识表”当隐含前提。
CLI 通过 public 的装配工厂创建本地 RunContext；工厂收显式 RuntimeResources，不 import app 或自动加载仓库根 `.env`。
平台通过同一装配入口注入其资源，平台 DB 配置不泄漏给 CodeQL 构建或验证沙箱。
新增包使用 `system/uv.lock` 锁定，独立安装验收从已构建 wheel 与冻结依赖清单进行，不能依赖 checkout 的隐含 import path。
导入约束既检查 AST，又检查隔离进程实际导入 / 运行，覆盖函数内动态导入与 CLI 间接依赖。

RunContext 中各端口按下表提供；默认实现属于科研包，平台可显式替换实现，但不可注入 ORM 会话充当上下文。

| 端口 | 最小操作与边界 |
| --- | --- |
| SourceReader | `read(snapshot, path, range)`、`list(snapshot, scope)`；返回真实字节 / 区间身份，只读且校验快照 |
| ArtifactStore / Resolver | `stage(execution_id, kind)`、`commit(staged)`、`read(ref)`；原子提交后才得到 ArtifactRef；只能解析已登记可读引用 |
| ExecutionStore | `create(spec)`、`append_event(event)`、`commit_manifest(manifest)`、`inspect(execution_id)`；独占输入、事件序号和修订比较 |
| ModelProvider | `generate(call_spec, response_schema)`；返回结构化输出和调用收据，预算 / Prompt / secret resolver 显式注入 |
| Scanner | `create_database(scan_spec)`、`analyze(database_ref, scan_spec)`；返回产物和工具收据，不直接改平台任务状态 |
| Retriever | `retrieve(corpus_snapshot, query, retrieval_policy)`；返回类型化命中与轨迹；不查平台用户可见范围 |
| Verifier | `validate(validation_spec)`；受控资源执行，返回 ValidationReceipt；开发与隐藏检验具备不同输入可见范围 |
| CheckpointStore | 提供固定版本 LangGraph saver，按 execution / graph version 隔离；不把框架对象放进持久化 RunSpec |
| ControlPort | `poll(execution_id)` 返回取消 / 授权撤销 / 版本状态；科研本地实现不联网查询平台 |
| EventSink | 接收已提交事件的通知；投递失败不丢 ledger，可重放；UI 故障不改算法结果 |

## 3. 三内核与平台职责细分

### 3.1 漏洞发现

内核拥有：CodeQL 建库 / 扫描 / SARIF 解析、只读独立粗筛、统一复核、前提与反证门、覆盖、批次反馈、根因关联建议。
平台拥有：上传限制 / 项目元数据、审计与阶段创建、已发布补充规则选择、人工候选确认、来源定位 UI、报告聚合。
CLI 拥有：源码输入冻结、选择 scan / scout / review / discover、显式参数、独立执行与本地人工决策。
粗筛与静态分支共享不可变源码，但不共享告警输入；组合发现的中间产物仍以引用交接。
Review 是发现内核的科研操作；候选 confirmed / excluded 的人工决策记录属于调用方，不由模型支配。

### 3.2 漏洞修复

内核拥有：冻结目标解释、语义取证、授权已读范围、候选生成、隔离补丁、native / OpenHands、技术验证和前后比较计算。
平台拥有：当前确认状态与归属、所选测试套件资格、自动创建验证任务、展示 Diff / 断言 / 历史、最终接受事务。
CLI 拥有：直接导入 TargetBundle / SuiteRef、显式决策来源、单次或批次执行、保存 patch / receipt；不调用平台接受接口。
修复结束只交付 ArtifactRef；前后比较可由 CLI 显式调用，平台的自动串联由 application 决定，不在算法 finalize 中调度。
前后源码读取与 Diff 下载统一经 manifest / ArtifactRef；不能靠平台目录约定找到科研产物。

### 3.3 规则生成

内核拥有：语料快照召回、材料准备、规格 / 模板 / 自由 QL 生成、编译、开发正反例反馈、项目单规则复扫、技术检验。
平台拥有：知识采集 / 索引管理 UI、可见集合解析、人工批准、原项目根因匹配确认、发布 / 停用与补充规则目录。
CLI 拥有：本地语料 / 显式向量资源、消融开关、批准与恢复、本地规则导出；不自动发布到平台。
批准入口使用通用 ApprovalDecision；其可信来源由调用方保证，内核负责哈希 / checkpoint / 动作身份校验。
独立技术检验适配器不向生成器暴露隐藏样本；论文评价器及其数据集仍留 benchmarks。

## 4. 当前文件 → 目标边界

“拆分”表示按函数职责提取，不是把整个目录直接改名。所有路径以前缀 `system/backend/app/` 为基准，另有注明者除外。

| 当前文件 / 组 | 内核侧提取 | 平台侧保留 / 改造 | TODO |
| --- | --- | --- | --- |
| `contracts/stages.py`、`scouting.py`、`unified_review.py` 等 | 纯科研请求 / 模型输出 / 验证值对象进入 contracts；有版本转换 | Web DTO 单独定义，旧字段经 bridge 转换，不复用 ORM 当公共协议 | DEC-002 |
| `contracts/experiments.py` | 实验配置迁 research-cli；模块 spec 引用 contracts | 平台 stage 输入 / audit_id 复用功能只留 legacy | DEC-009 |
| `domain/audit.py` | 工具计划、内核错误与取消类型提纯 | 平台状态 / API 错误映射自有类型 | DEC-002、004 |
| `runtime/stages.py`、`scans.py`、`checkpoints.py` | 图调用与检查点接口抽到 research/runtime；不携 ORM | claim、队列状态、平台失败投影留 application / jobs；旧版 runtime 冻结 | DEC-004、011 |
| `services/stage_lifecycle.py`、`stage_actions.py` | 无直接搬迁；抽通用输入规则到 contracts 或内核校验器 | 平台归属、任务并发、创建、批准 / 取消 / 恢复、重试留 application | DEC-005、011 |
| `services/uploads.py`、`adapters/archive.py`、`snapshot.py` | 安全解包 / 快照算法可复用到 research source adapter | 平台上传配额、AuditRun 创建保留；CLI 输入导入不调用 create_run | DEC-004、009 |
| `services/scanning.py`、`dual_scanning.py` | 扫描、双分支执行 / 汇总进入 discovery | 自建 StageRun、已发布规则查询、AuditRun 更新拆出 | DEC-006 |
| `services/scouting.py`、`scout_inspection.py`、`scout_continuation.py`、`scout_localization.py` | 窗口、取证、补审范围与中断续接输入进入 discovery | Candidate / StageRun 读写拆到投影；展示翻译归平台 | DEC-006 |
| `services/review.py`、`unified_review.py`、`review_batch.py`、`review_pool.py` | 复核编排、候选池与批次算法进入 discovery | audit / stage 仓储查找拆输入物化，不进入内核 | DEC-006 |
| `services/review_results.py`、`unified_review_results.py` | 证据门、结论校验、结果 Bundle 构建 | ORM 写入、历史视图拼接进入 projection / query | DEC-006、011 |
| `review_feedback.py`、`review_recovery.py`、`review_verdict_gate.py`、`review_classification.py` | 未知前提、取证反馈、反证门、语义分类 | 平台历史读取、UI 分类与中文状态解释拆开 | DEC-006 |
| `discovery_context.py`、`discovery_framework_facts.py`、`route_obligations.py`、`read_tools.py`、`inspection_tools.py` | discovery 或 evidence 的纯上下文 / 只读工具 | 不再隐式访问平台历史 | DEC-004、006 |
| `services/evidence.py`、`knowledge_evidence.py`、`candidate_sources.py` | SourceReader、真实证据 / 知识来源核验、EvidenceRecord | ORM 持久化与已授权源码展示归 query / bridge | DEC-004 |
| `context_materials.py`、`semantic_inspection.py`、`inspection_progress.py` | evidence / runtime 的具名材料步骤、冻结调用、覆盖进展 | 不保留一份不断扩大的共享 utils；ORM 解析移除 | DEC-004 |
| `services/repair.py`、`repair_semantics.py`、`repair_openhands.py` | repair 执行、候选反馈、最终 RepairResult | ORM 保存、阶段状态、自动验证投递剥离 | DEC-007 |
| `repair_inputs.py`、`repair_source_tools.py`、`repair_consistency.py`、`repair_candidate_validation.py` | 授权范围、证据可见区间、完整性 / 一致性、候选检验 | 最新平台确认查询经 ControlPort / 接受前检查，不查询 ORM | DEC-007 |
| `repair_integrity.py`、`repair_requirements.py`、`repair_suite_checks.py`、`repair_runtime_diagnosis.py` | repair 的输入身份 / suite 断言 / 失败归因 | 面向平台接受的最新状态门在 application | DEC-007、011 |
| `verification_suites.py`、`verification_results.py`、`repair_comparison.py` | suite 生成 / 冻结、before / after 计算与收据核验 | owned-suite、acceptance_ready、自动 enqueue、对外比较视图归 application / presentation | DEC-005、007 |
| `services/rules.py`、`rule_synthesis.py` | rules 执行、生成 / 反馈、技术检验和规则 Bundle | ORM、批准来源、发布条件与事务拆开 | DEC-008 |
| `rule_materials.py`、`rule_context.py`、`rule_preparation_context.py`、`rule_feedback.py`、`rule_output.py` | rules 的来源 / 检索 / 规格准备与生成输出核验 | 读 Candidate / Evidence 改输入 Bundle 解析 | DEC-008 |
| `rule_development.py`、`rule_project_validation.py`、`rule_database_identity.py`、`rules_execution.py` | 编译 / 例子 / 原项目规则执行与 DB 身份校验 | 当前 RuleVersion 可用性、人工项目匹配、发布目录归平台 | DEC-008、011 |
| `rule_drafts.py`、`rule_holdouts.py` | 草稿内容核验、独立技术检验适配接口；内置微样本移独立验证资源 | 草稿查表、批准与发布门归 application；历史数据集 ID 兼容 | DEC-008 |
| `workflows/scanning.py`、`dual_scanning.py`、`scouting.py`、`review.py`、`unified_review.py` | discovery/workflow，节点只用内核步骤和 RunContext | 平台不再直接 import 这些内部 builder | DEC-006 |
| `workflows/repair.py`、`repair_openhands.py`、`rules.py` | 对应内核 workflow，保留检查点 / 人工暂停但去除 StageRun 依赖 | legacy 图留旧执行恢复直到生命周期结束 | DEC-007、008 |
| `adapters/ai/*`、`ports/model.py` | 无 ORM / 全局配置的 ModelProvider、冻结调用与外部用量 | 旧 bind_stage 迁成平台装配与模型事件消费 | DEC-004 |
| `adapters/codeql/*`、`ports/scanner.py`、`adapters/repair/*` | research adapters，工具路径 / 镜像 / 限额由参数注入 | 已发布资格与平台根目录选择不在 adapter | DEC-004、006～008 |
| `adapters/retrieval/*` | 通用 chunk / ranking / routing 与 RetrievalPort；本地 / 可选 PG 实现 | KnowledgeChunk 管理与索引作业留平台，通过语料导出建立快照 | DEC-004、008 |
| 语法、源码导航、绑定、常量 / 操作证据等 `adapters/*` | research adapters / evidence；可复用成熟框架，保留来源限制 | 不重复创建平台版本 | DEC-004 |
| `adapters/artifacts.py`、`node_timing.py`、`experiment_receipts.py` | 显式根目录的 ArtifactStore、事件 / 时序账本、科研收据 | 平台授权下载与旧收据 reader 留平台；去掉 StageCancelled / report service 反向依赖 | DEC-004 |
| `candidate_decisions.py`、`candidate_reviews.py`、`candidate_classification.py` | 纯判断规则可提成不依赖 ORM 的值对象处理 | 人工决定、当前状态查询、聚合分类留 application / presentation | DEC-011 |
| `candidate_localization.py`、`repair_localization.py`、`review_presentation.py`、`result_explanations.py` | 无科研算法搬迁 | 展示翻译、中文解释归 presentation；需模型时是平台展示任务，不算三内核科研调用 | DEC-011 |
| `reports.py`、`report_generation.py`、`report_materials.py`、`report_overview.py`、`readable_reports.py`、`ai_report_markdown.py`、`workflows/report.py` | 仅提取算法所需的通用无副作用材料格式 | 报告是平台聚合 / 可选叙述功能；独立实验导出不依赖它 | DEC-011 |
| `persistence/*`、`models.py`、`core/db.py`、`alembic/*` | 不进入 research | 保留平台；新增 binding / entity map / inbox / outbox 迁移 | DEC-005 |
| `api/routes/*`、`jobs/*` | 不进入 research | 薄路由 / 薄任务；调用应用用例，显式状态和错误映射 | DEC-011 |
| `app/cli/*` | 新 research-cli 按行为重建，算法从 public 直接调用 | 旧命令标 legacy，暂存旧 DB 执行记录查询能力 | DEC-009、013 |
| `system/scripts/benchmarks/formal_runtime.py` 与活跃评测入口 | 新运行适配器只使用 research.public / CLI | 旧冻结桥与结果不改写；评分 / oracle 仍在 benchmarks 体系 | DEC-010 |
| `system/frontend/src/api/*`、`features/*` | 无需接触科研包 | 首期兼容旧 DTO；后续逐步绑定展示 Schema，Diff 走原平台 URL | DEC-011 |

未单列的新文件按依赖方向归属，DEC-001 产生逐文件清单；不凭文件名决定归属，特别是 localization 同时有算法定位与展示翻译两种语义。

## 5. 薄桥接层如何保持薄

桥接只承担三件事：物化输入、调用公共接口、映射已校验结果；不重新实现科学判断。
建议按职责组织 `request_mapping.py`、`runner.py`、`projection_mapping.py`，体量增大时再按模块拆。
平台 application 先检查归属 / 当前确认 / 选定 suite / 规则可用性，冻结输入；bridge 不能偷偷选择“最新”记录。
request mapping 将 ORM 数据转换成 contracts，在受控 ledger 中写候选 / 证据 / 决策包并冻结输入摘要。
runner 接受已绑定的 execution，装配平台资源，调用 public；不把 Session 或 ORM 对象传进内核。
projection mapping 输出待持久化实体数据；仓储事务、投影去重与 outbox 补偿由 application / persistence 承担。
中文解释、页面状态、源代码定位展示放 presentation；技术验证 / evidence gate 继续在内核，避免桥接变成新 service 大杂烩。
平台内核执行成功但展示 / 投影失败是两个状态；重放投影不得再次调用 LLM。

## 6. 状态与身份的唯一归属

| 事实 | 记录位置 | 修改原则 |
| --- | --- | --- |
| 科研输入、算法版本、执行事件、原始结果 | 科研 ledger / manifest | 输入不可变、事件追加、清单按 revision 发布 |
| LangGraph state / pending approval | 每 execution 检查点 namespace | CLI 本地 / 平台注入分别隔离，旧检查点保留原 executor |
| 模型 / 工具调用和用量 | 每 execution 调用账本 | 对 call_id 去重，未知外部结果必须保留未知 |
| 用户所见任务状态、调度租约、投影状态 | 平台 DB | 与科研执行绑定，不能反向修改科研结论 |
| 人工决策与批准 | CLI 本地 ledger 或平台 DB | caller 负责身份；每条动作生成不可变协议记录 |
| 接受补丁 / 发布规则 | 平台 DB | 当前证据 / query / patch / suite 哈希及最新人工状态均需再次核验 |
| 独立准确率 / oracle / 统计 | benchmarks 独立 evaluation ledger | 不回写成生成输入；绑定新尝试 / 冻结 epoch |

平台在运行中撤销目标确认，可通过注入 ControlPort 在下一安全边界停止；外部调用正在进行时不声称即时取消。
CLI 使用自己的本地 ControlPort，不连平台查询权限。任意入口都不能绕过源码完整性与写范围校验。
不可变源码和字节级产物可显式共享 / 导入；执行账本、租约、取消标记、检查点、平台会话不得隐式共享。

## 7. 迁移策略和停止条件

先只加 contracts / public / adapter 并把旧 service 包成临时 facade；每抽离一个能力即迁其测试与调用点。
独立 CLI 不能通过 facade 或旧 app/runtime 过渡来宣称已分离；其完成门就是“不安装 backend 仍可真实运行三模块”。
facade 仅供平台迁移，职责是输入 / 输出映射，禁止保留一份科研算法副本。
新任务创建时冻结引擎、协议与方法版本；旧运行中任务恢复仍按旧图，不能混用新 state。
先验证不变输入 / 工具结果下的机械等价，再做固定小样本真实模型可行性验证；随机响应差异单独归因。
通过新旧比较前不切换默认；失败时保留产物、标新尝试、回到上游门，不能覆盖历史失败。
只要 CLI 仍需要 User / Workspace / AuditRun / StageRun、运行时 import app 或访问平台数据连接，就视为解耦未完成。
只要平台服务仍从算法 finalize 自动调用 API / Celery、或桥接重做算法判定，就视为代码边界未完成。

## 8. 配套文档改造顺序

DEC-013 更新 `design/architecture.md` 的真实依赖图，以及 `design/experiment-cli.md` 中“共享平台 runtime”的旧说明。
更新 `system/backend/README.md`，把平台运行和科研 CLI 安装 / 配置分别指向独立说明。
新增 `system/research/README.md`、`system/research_cli/README.md`：明确三内核 public、独立运行目录、外部工具与输出口径。
仓库根 README 只列两条入口；工具安装 / 源码快照 / 科研协议不埋在平台启动说明中。
本次仅在导航登记待实施计划，不把未来架构写成已经交付的事实。

</details>
