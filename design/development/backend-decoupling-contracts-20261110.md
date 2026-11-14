# 三个科研内核的数据交互契约 v1

当前实现、版本与交付范围见[交付摘要](backend-decoupling-delivery-20261113.md)及可执行 contracts Schema。本文保留初始提案；其中计划中的通用 retry、实验管理或逐文件清理不是当前能力声明。

<details>
<summary>2026-11-10 初始设计提案原文（历史）</summary>

# 三个科研内核的数据交互契约 v1（待实施）

提案时间：2026-11-10T14:08:02+08:00。主任务与状态见[解耦 TODO](backend-decoupling-todo-20261110.md)。
这是目标协议，不是当前 API 说明。DEC-002 负责把本规格变为可执行 Schema、类型与兼容性测试。
初版类型和九种操作的 Schema 已落入 `system/contracts`，见[实现与验证记录](backend-decoupling-progress-20261110.md)；
运行语义、真实算法和平台映射仍按后续 TODO 实施，不能据此认为全部协议动作已可执行。

## 1. 公共接口与两条调用路径

科研 CLI → `semflow_research.public.discovery / repair / rules`，Web → 平台应用用例 → 薄桥接层 → 同一 public。
三个模块分别提供 `execute(spec, context) -> ResultEnvelope`；context 是每次执行独有的端口集合，不是可序列化输入。
公共 `runs` 接口提供 inspect / resume / cancel / retry，针对科研 execution ID，不接收平台 stage ID。
`inspect(execution_id, context)` 读取清单；`resume(command, context)` 返回同执行的新结果；`cancel(command, context)` 登记取消请求；
`retry(execution_id, new_execution_id, context)` 克隆冻结方法与参数、创建新输入和账本，不重置旧执行。
CLI / Web 都不导入内核的内部 service；CLI 不导入平台桥接层。初期不定义新的 HTTP 服务。

| module | operation | 能力边界 |
| --- | --- | --- |
| discovery | scan / scout / review / discover | 独立静态、独立粗筛、基于冻结候选复核、组合发现；discover 不自动人工确认 |
| repair | generate / build_suite / verify | native 或 OpenHands 修复、验收套件生成、冻结补丁的前后验证 |
| rules | generate / validate | 规则生成与开发反馈、冻结规则的批准后技术检验；不含发布 |

组合发现有父 execution 与各子 execution，子执行也有独立 manifest；跨模块编排由 CLI 实验计划或平台应用层负责。
生成路径和独立评分路径分开；科研模块可独立调用，不能强制先建平台审计或运行其他模块。

## 2. 通用值对象与引用

所有协议模型 `extra=forbid`，UUID 用标准字符串；时间用 RFC3339 带偏移，持久化推荐 UTC，文档 / TODO 使用北京时间。
表中 `?` 表示可空，`[]` 表示数组。大型数组以带 Schema 的 JSONL 产物承载，不用无限扩张的消息体。

| 类型 | 必填字段与约束 |
| --- | --- |
| ArtifactRef | `artifact_id:UUID, owner_execution_id:UUID, kind:enum, schema_version:string, path:string, sha256:hex64, size_bytes:int>=0, media_type:string`；path 是该执行受控根目录下相对 POSIX 路径 |
| BundleRef | `artifact:ArtifactRef, entity_ids:UUID[]?`；指向已冻结类型化记录；未给 entity_ids 表示完整集合 |
| SourceSnapshot | `snapshot_id:UUID, tree_sha256:hex64, archive:ArtifactRef, manifest:ArtifactRef, languages:Language[], origin:SourceOrigin`；单执行选定一种分析 language |
| SourceOrigin | `kind:archive\|git\|directory, revision:string?, label:string?`；不含凭据与宿主绝对路径 |
| SourceLocation | `snapshot_id:UUID, path:string, start_line:int>=1, end_line:int>=start_line, file_sha256:hex64`；字节 / 列范围可选，但注明编码和基数 |
| EvidenceRecord | `evidence_id:UUID, execution_id:UUID, snapshot_id:UUID, kind:code\|query\|tool\|knowledge, content:ArtifactRef, digest:hex64, location:SourceLocation?, provenance:EvidenceProvenance` |
| EvidenceProvenance | `producer:string, tool_version:string?, call_id:UUID?, input_refs:ArtifactRef[]`；query / tool 证据带实际调用与原始输出引用 |
| EntityRef | `execution_id:UUID, entity_id:UUID, bundle:ArtifactRef`；禁止仅靠标题、规则 ID 或路径作为漏洞实例身份 |
| DecisionRecord | `decision_id:UUID, target:EntityRef, snapshot_id:UUID, status:confirmed\|excluded\|pending\|insufficient, actor:ActorRef, reason:string, evidence_refs:EntityRef[], created_at:datetime` |
| ActorRef | `kind:human\|experiment_fixture, id:string, provenance:ArtifactRef?`；无平台 user 外键；平台只接受其验证过的人类决策 |
| TargetBundle | 冻结的 candidates / evidence / decisions 三类 BundleRef 与共同 snapshot_id；供修复和基于漏洞的规则任务使用 |
| RuleRef | `rule_id:UUID, version:string, purpose:RulePurpose, language:Language, query:ArtifactRef, modules:ArtifactRef[], dependencies:ArtifactRef, query_hash:hex64` |
| SuiteRef | `suite_id:UUID, definition:ArtifactRef, suite_hash:hex64, target_refs:EntityRef[], source:human\|model_generated\|external_fixture, image_digest:string` |
| CorpusSnapshot | `snapshot_id:UUID, manifest:ArtifactRef, digest:hex64, collections:CollectionRef[], embedding:EmbeddingIdentity?` |
| CollectionRef | `name:reference\|rule_example, version:string, document_ids:UUID[], digest:hex64`；空集合和缺失集合需区分 |
| EmbeddingIdentity | `provider:string, model:string, revision:string, dimensions:int, index_digest:hex64`；纯 BM25 可为空 |

Language v1：`python | javascript`；TypeScript 沿用现有 JavaScript 工具能力边界，不借重构声明新增语言支持。
RulePurpose：`review_anchor | vulnerability_detector | framework_model`，不得把 anchor 命中当漏洞检测成功。
Artifact kind 至少包括 source_archive / source_manifest / evidence_bundle / candidate_bundle / decision_bundle / sarif / codeql_database /
patch / patched_source / repair_attempts / suite / validation_receipt / query / rule_modules / corpus_manifest / retrieval_trace / model_call /
log / checkpoint / result_bundle / result_manifest；按 Schema 明确枚举，未知 kind 需版本协商。

引用解析由注入的 Resolver 完成：调用方在 ledger 登记可读执行与快照，不能拿任意外部路径伪装 ArtifactRef。
跨执行证据允许显式上游引用且需同一快照；新执行自己生成的证据归当前执行，不重写上游实体身份。
artifact sha256 是实际字节哈希；tree_sha256 按版本化源码清单算法计算，清单记录排序、路径、文件字节哈希和排除规则。
旧 snapshot_digest 不直接当新哈希：保留 legacy_algorithm / digest，对照核验后生成新 manifest；不改旧记录。
绝对路径、`..`、反斜杠逃逸、符号链接越界、错误大小 / 哈希、跨作用域引用均失败，不返回“缺少证据但继续”。
证据结构验证后，还必须校验源码行、内容哈希、工具输出与实体归属；knowledge 不能单独证明漏洞成立。

## 3. RunSpec：不可变输入信封

| 字段 | 类型 / 语义 |
| --- | --- |
| schema_version | 固定 `semflow.research.run/1.0` |
| execution_id | UUID，由调用方分配并独占登记；同 ID 不同输入必须冲突 |
| module / operation | 上表可判别组合，不能接受任意字符串阶段 |
| lineage | `{experiment_id:UUID?, sample_id:string?, repetition:int?, epoch:string?, parent_execution_id:UUID?, retry_of:UUID?, upstream:ArtifactRef[]}` |
| source | SourceSnapshot；任务基准源码与目标指向该快照，verify 的补丁后快照以独立字段显式关联 |
| language | Language，与 source.languages、规则 / suite 的语言一致 |
| implementation | `{method_id:string, method_version:string, code_digest:hex64, dependency_lock_digest:hex64}` |
| prompts | PromptSnapshot[]；纯静态操作为空数组，模型操作提供全部所用角色的冻结 Prompt |
| model | ModelProfile?；纯静态操作可空，模型操作必须提供 |
| policy | ExecutionPolicy；必须完整冻结，不从平台 / CLI 隐式取默认值 |
| inputs | 按 module + operation 判别的类型化输入，见后文 |

PromptSnapshot：`role:string, template_id:string, version:string, content:ArtifactRef, sha256:hex64`；role 必须唯一，sha256 必须与 content 相同。
ModelProfile：`provider, model, revision?, endpoint_profile, temperature?, thinking_mode?, output_schema_version`。
endpoint_profile 是无密钥的逻辑名；实际 URL / secret / 可用工具路径由调用方 RuntimeResources 解析，实际配置脱敏记入运行账本。
未提供或供应商不返回 revision，记录 unknown；固定请求配置不等于供应商响应确定。
ExecutionPolicy：`mode:bounded|progress, max_calls:int?, max_tokens:int?, max_seconds:int?, per_call_timeout_seconds:int, tool_timeout_seconds:int, max_attempts:int, max_context_chars:int, resource_profile:string, decision_policy:human_only|experiment_declared`。
bounded 的三项总限额都必填且大于零；progress 必须显式标识没有哪些累计上限，仍受单次、候选次数、资源和停滞边界限制。
模块专用预算 / 修复取证范围 / 粗筛窗口限制在 inputs 的已版本化 policy 中，不能仅用一个通用 max_attempts 替换旧策略。
装配层先解析完整默认值并冻结，再计算 input_digest；不同入口同一 spec 的语义必须一致。
input_digest 对 RunSpec 的 UTF-8 规范 JSON 计算 SHA-256：键排序、紧凑分隔符、禁止 NaN / Infinity、保留数组顺序，规范算法也需版本化。
execution_id 和 lineage 属于输入摘要；重试的新摘要允许变化，另存去除执行身份后的 method_input_digest 用于输入等价对照。
credentials、隐藏 oracle、真实上传目录、平台数据库连接和 UI 文案不能进入 RunSpec。

## 4. 结果、清单与事件

| ResultEnvelope 字段 | 类型 / 约束 |
| --- | --- |
| schema_version / execution_id / input_digest | `semflow.research.result/1.0` / UUID / hex64；与冻结输入核对 |
| module / operation / implementation | 与 RunSpec 相同 |
| execution_status | `created \| running \| awaiting_input \| completed \| failed \| cancelled \| interrupted` |
| completeness | `{status:full\|partial\|none, reasons:string[], planned_units:int?, completed_units:int?, unassessed_refs:EntityRef[]}` |
| result | 按 module / operation 判别的类型化结果；尚无结果为 null，失败仍允许已核验的部分结果 |
| validation | ValidationReceipt[]；没有执行则显式 not_run / not_evaluated，不能默认 passed |
| failure | `{code, category, message, retryable:bool, phase, detail:ArtifactRef?}` 或 null；failed 时必须非空 |
| artifacts | ArtifactRef[]；实际落盘且校验通过的产物 |
| usage | `{calls:int, input_tokens:int?, output_tokens:int?, wall_seconds:number, tool_seconds:number?, by_provider:UsageEntry[], completeness:complete\|partial\|unknown}` |
| timestamps | `{created_at, started_at?, ended_at?}` |
| pending_action | ApprovalRequest?；awaiting_input 时必须有，其他状态为空 |
| manifest | ArtifactRef，指向 ResultManifest；manifest 本身不递归包含自己的引用 |

UsageEntry：`provider:string, model:string, call_ids:UUID[], calls:int, input_tokens:int?, output_tokens:int?, completeness:complete|partial|unknown`。
调用原始账本另记失败 / 重试 / 超时；摘要聚合不得丢弃失败调用已发生的用量。
ResultManifest 是每个边界版本的不可变清单：`execution_id, revision:int, input_digest, spec:ArtifactRef, result:ArtifactRef, artifacts:ArtifactRef[], final_event_seq:int, previous_manifest:ArtifactRef?`。
result 产物存储去掉 manifest 字段的信封内容，避免清单与结果哈希循环；读 API 验证清单后补 manifest 引用。
运行中也可发布新 revision；只有已完整落盘的 immutable manifest 可作为平台投影依据。
completed 只表示请求的操作执行结束；检查未过也可能 completed + validation.failed；不得推断漏洞真实、补丁已接受或规则已发布。
发现必需分支工具失败为 failed + partial result；所有分支执行完但覆盖不全可 completed + partial。未评估候选不排除。

Event：`schema_version, event_id:UUID, execution_id, seq:int>=1, occurred_at, type, phase_code, payload`。
type 包括 execution_started / phase_changed / evidence_recorded / candidate_recorded / model_call_finished / artifact_committed /
validation_finished / awaiting_input / execution_finished；payload 使用按 type 判别的模型。
seq 在单执行内单调递增；事件先持久化，订阅投递允许至少一次和乱序；平台按 execution_id + event_id 去重，按 seq 补洞。
事件仅用作实时展示 / 触发拉取；最终事实由清单重建。用量对 call_id 去重，供应商未知 token 为 null，不填 0，不伪造费用。

## 5. 漏洞发现内核

| 输入 | 具体字段 |
| --- | --- |
| ScanInput | `query_pack:{name,version,digest}, suite:{name,digest}, supplemental_rules:RuleRef[], build_profile:string` |
| ScoutInput | `scope_paths:string[], window_policy:{version,max_windows,max_steps_per_window,max_calls}, continuation:ArtifactRef?` |
| ReviewInput | `targets:BundleRef, evidence:BundleRef, source_execution_ids:UUID[], policy:ReviewPolicy` |
| DiscoverInput | `scan:ScanInput?, scout:ScoutInput?, review:ReviewPolicy?, required_branches:(scan\|scout)[]`；至少一个分支；显式选择是否统一复核 |

ReviewPolicy：`version:string, batch_size:int, max_batches:int, supplement_insufficient:bool, max_steps:int, max_context_chars:int, scope_paths:string[]`。
独立 ReviewInput 也须显式传入该 policy；组合发现的 targets / evidence 由已完成子执行产物冻结，不从平台历史隐式补齐。
required_branches 必须非空且是实际启用分支的子集；每个启用分支即使非必需，其失败和未评估也不得从结果中消失。
review 的 targets 可是静态告警与粗筛候选的冻结并集；不得把评测真值作为发现候选输入。
scout 只获源码和自身策略，不接收静态告警、规则命中或关键词锚点；组合运行不得把 scan 的结果放入 scout context。
发现输入引用补充规则时，平台负责已发布资格；科研 CLI 负责显式规则来源。内核只验证内容、依赖和用途。

DiscoveryResult：`static_findings:BundleRef?, candidates:BundleRef, evidence:BundleRef, assessments:BundleRef?, coverage:CoverageReport, branches:BranchOutcome[], root_relations:ArtifactRef?`。
CandidateRecord：`candidate_id, execution_id, origin:codeql|scout|review, title, description, weakness, primary_location, identity_key, static_finding_ref?, related_target?, novelty, evidence_refs:EntityRef[]`。
identity_key 是版本化实例定位键；不同位置 / 来源保留触发路径，root_relations 是关联建议，不直接合并或删除原始候选。
AssessmentRecord：`assessment_id, candidate_ref, conclusion:supported|excluded|pending|insufficient, checked_premises, unknown_premises, evidence_refs, counter_evidence_refs, reason`。
excluded 必须有实际反证；supported 也不是人工 confirmed。未复核候选仅在 coverage 中保留，不能填“已排除”。
CoverageReport：`status:full|partial|none, scope_manifest:ArtifactRef, inspected_units:ArtifactRef, missing_units:ArtifactRef, reasons:string[], reviewed_candidate_refs:EntityRef[], unreviewed_candidate_refs:EntityRef[]`。
BranchOutcome：`branch:scan|scout|review, execution_id, status, result_manifest:ArtifactRef?, failure?`；分支失败不能写空 findings 表示成功。

## 6. 漏洞修复内核

| 输入 | 具体字段 |
| --- | --- |
| RepairGenerateInput | `engine:native\|openhands, targets:TargetBundle, patch_scope:PatchScope, validation_plan:RepairValidationPlan, suite:SuiteRef?, method_policy:RepairMethodPolicy` |
| SuiteBuildInput | `targets:TargetBundle, requested_behavior:ArtifactRef, runtime_profile:string`；仅生成待审套件，不等于测试有效 |
| RepairVerifyInput | `repair:EntityRef, patch:ArtifactRef, patched_source:SourceSnapshot, suite:SuiteRef, validation_plan:RepairValidationPlan` |
| PatchScope | `writable_paths:string[], readable_paths:string[], max_changed_files:int, enforce_observed_ranges:bool`；只写允许文件内已读且哈希一致的范围 |
| RepairValidationPlan | `syntax:bool, project_tests:TestPlan?, rescan:ScanInput?, before_after:bool`；未启用项目测试不得伪造通过 |
| TestPlan | `runner:python_pytest\|javascript_test, suite:SuiteRef?, resource_profile:string`；不接受任意未审查宿主 shell 命令 |
| RepairMethodPolicy | `version, max_candidates, inspection_limits, feedback_policy, selected_suite_feedback:bool, baseline_reuse:bool`；记录真实旧版本分支 |

内核检查 target / evidence / decision 的快照与范围，human_only 要求 confirmed 的人类决策。
科研 CLI 可显式使用 experiment_declared + experiment_fixture 决策并记录协议来源；该结果不能在平台投影时变成人类 confirmed。
模型不能自行创建允许修复的 DecisionRecord；外部实验目标描述是显式任务输入，不得携带隐藏测试答案。
运行中取消 / 决策撤销经 ControlPort 生效；平台接受时仍重新检查当前决策，旧冻结决策不替代最新状态。

RepairResult：`repair_id:UUID, target_refs:EntityRef[], attempts:ArtifactRef, selected_attempt_id:UUID?, patch:ArtifactRef?, patched_source:SourceSnapshot?, checks:ValidationReceipt[], outcome:checks_passed|needs_review|no_patch, semantic_context:ArtifactRef, original_snapshot_unchanged:bool`。
AttemptRecord：`attempt_id, ordinal, context_digest, proposal:ArtifactRef, patch:ArtifactRef?, patched_tree_sha256?, checks:ValidationReceipt[], diagnosis:ArtifactRef?, selected:bool`。
即使全部候选失败，也保留每轮产物和失败归因；不会自动接受“最后一个”失败补丁。
SuiteBuildResult：`suite:SuiteRef, review_required:bool, generation_evidence:BundleRef`。
RepairVerifyResult：`repair_ref, identity:{before_tree_sha256,patch_sha256,after_tree_sha256,suite_hash,image_digest,target_digest}, receipt:ValidationReceipt`。
比较中分别记录前置漏洞复现、补丁后阻断、正常功能保持；baseline 复用只允许全部身份一致，证据不一致则 stale。
模型语义一致性是单独检查项，不替代独立 oracle；内核无 accepted 状态，无“自动修改原项目”行为。

## 7. 规则生成内核

| 输入 | 具体字段 |
| --- | --- |
| RuleGenerateInput | `purpose:RulePurpose, requirement:string, target:TargetBundle?, source_paths:string[], strategy:auto\|model\|extend\|new_query, corpus:CorpusSnapshot, retrieval:RetrievalPolicy, generation:RuleMethodPolicy, development:DevelopmentPlan, acceptance:RuleAcceptancePlan` |
| RetrievalPolicy | `mode:bm25\|vector\|hybrid, collection_routing:bool, corpus_document_ids:UUID[]?, top_k:int, version:string`；省略白名单和空白名单语义不同 |
| RuleMethodPolicy | `version, full_feedback, generation_constraint, progress_feedback, compact_context, source_preparation_context, rag_before_inspection`；开关固定，禁止自由 kwargs |
| DevelopmentPlan | `compile:bool, development_fixtures:ArtifactRef?, project_replay:bool, query_pack:ArtifactRef`；模型生成例与外部开发例标注来源 |
| RuleAcceptancePlan | `fixture_validation:bool, holdout:HoldoutHandle?`；在生成前冻结检验计划，仅 evaluator 可解析隐藏内容 |
| RuleValidateInput | `rule:EntityRef, query:RuleRef, fixtures:ArtifactRef, approval:ApprovalDecision, holdout:HoldoutHandle?, project_replay:ArtifactRef?` |
| HoldoutHandle | `dataset_id:string, version:string, digest:hex64, evaluator_profile:string`；只传身份，不传隐藏例或预期答案给生成器 |

自动选择检索模式只在入口解析阶段进行，冻结实际模式及依据；vector / hybrid 所需索引不匹配或不可用时显式报错，不静默换方法。
target 可空以支持独立规则需求；选中目标时必须满足 TargetBundle 的冻结证据与决策约束，不强制先有修复结果。
RuleResult：`rule_id:UUID, rule:RuleRef, purpose, strategy, coverage_analysis:ArtifactRef, fixtures:ArtifactRef, retrieval_trace:ArtifactRef, development_checks:ValidationReceipt[], project_replay:ValidationReceipt?, technical_validation:ValidationReceipt?, outcome:draft|checks_passed|needs_revision`。
检索轨迹必须记录 collection / document / chunk ID、版本 / digest、排名、召回模式与实际用于生成的引用，不用平台 KnowledgeChunk ORM 对象。
项目复扫记录 target_detected / target_missed / already_covered / not_evaluated，关联目标实例与 SARIF，而非仅统计告警数。
framework_model 不借用 detector 的通过标准；能力 / 验证器不支持时返回 unsupported_operation 或 not_evaluated，不降级用途。
模型样例经批准才做正式技术检验；独立 holdout 验证后该轮候选冻结，不能把 holdout 反馈回同一生成循环。
内核不提供 published / retired 状态；平台结合批准、独立验收、项目匹配确认和当前哈希执行发布。
generate 若请求正式样例检验，在完成开发反馈后暂停；resume 仅携批准，按已冻结 acceptance 执行检验，不新增检验参数。
独立 validate 可用于新执行中重验上游规则；需核验上游批准的 action 来源和主体哈希，不把批准归属改成本次 execution。

## 8. 验证与人工动作

ValidationReceipt：`validation_id, kind, status, subject_refs:ArtifactRef[], target_refs:EntityRef[], identity_digest, checks:CheckResult[], tool_profile, raw_output:ArtifactRef?, started_at?, ended_at?, meaning`。
kind：syntax / project_tests / rescan / before_after / semantic_consistency / rule_compile / rule_development / rule_project_replay / rule_holdout。
status：`passed | failed | error | not_run | not_evaluated | inconclusive | stale`；失败断言与环境工具错误分开。
CheckResult：`check_id, category, status, expected:ArtifactRef?, observed:ArtifactRef?, evidence:ArtifactRef[], reason?`；隐藏预期引用只在 evaluator ledger 可见。
平台 / CLI 的展示投影只读取有权限的 receipt 视图；不得因“存在 receipt”推断 passed。

ApprovalRequest：`action_id:UUID, kind:approve_rule_fixtures|review_suite, execution_id, checkpoint:ArtifactRef, subject_refs:ArtifactRef[], subject_digest, required_actor:human, reason_schema_version, created_at`。
ApprovalDecision：`decision_id:UUID, action_id, actor:ActorRef, approved:bool, reason, subject_digest, created_at`；绑定当前产物，重复同 ID 同内容幂等，内容不同冲突。
生成图到达人工边界后，先落盘清单和检查点，再返回 awaiting_input；Worker / CLI 进程可以退出。
拒绝批准保持该执行的等待状态并记录决策；重新批准或显式取消均需新命令；修改样例则创建新执行，旧批准失效。

ControlCommand：`command_id:UUID, execution_id, action:resume|cancel, expected_revision:int, checkpoint_digest:hex64?, approval:ApprovalDecision?, reason`。
resume 要求合法等待状态、检查点、主体哈希和批准一致，返回同 execution_id；不重新跑生成节点。
cancel 是请求；ControlPort 在安全边界确认后终态 cancelled，不能把仍运行的外部命令伪装成已停止。
interrupted 恢复先查已提交外部调用记录；“可能已调用但无结果”显式 external_outcome_unknown，人工决策后新尝试，不能盲重放。
retry 创建新 execution_id + retry_of，原执行 / 事件 / Prompt / 输入不改；预算重新计数但保留历史关联。
平台对外仍可兼容其旧取消语义，内部要保留 cancel_requested 与实际终止的区别。

## 9. 平台映射、提交与幂等

| 平台实体 / 字段 | 科研数据来源 | 写入约束 |
| --- | --- | --- |
| AuditRun | 源码快照 + discovery execution bindings | audit 是容器；不能把 audit_id 当 execution_id |
| StageRun | module / operation 的一个或多个明确绑定 | discovery 聚合与子阶段用 role 区分；不靠相同 UUID 关联 |
| Evidence / Candidate | EvidenceRecord / CandidateRecord / AssessmentRecord | 独立 ID 映射；Candidate.status 不因 supported 改为 confirmed |
| Decision | 经平台身份验证的人工动作 | 科研 experiment_fixture 决策只作来源显示，不写成平台确认 |
| RepairRecord | RepairResult 与前后比较 receipt | accepted / accepted_by 仍由平台接受事务写入 |
| RuleVersion | RuleResult、fixtures、query hash、检验 receipt | 发布 / 停用独立事务；内容或依赖变化需新版本和重新验收 |
| 日志 / Diff / 材料 URL | 类型化 ArtifactRef | 平台授权后下载；拒绝任意路径，返回原始字节，不重算 Diff |
| 前端 phase / summary / localized 字段 | 平台 ProgressView / DetailView | 内核 phase_code 映射，未知值显式显示；不污染原 manifest |

新增 execution_binding：`execution_id(unique), audit_id, stage_id?, role, engine, contract_version, input_digest, latest_manifest_digest?, projected_revision, projection_status`。
每个科研执行只能有一个平台执行归属；一个 audit 可绑定多个执行，聚合与子阶段各有 role。
新增 research_entity_map：唯一 `(execution_id, entity_kind, research_entity_id)` → platform ID；证据引用先映射，后写候选。
新增 inbox / outbox：inbox 唯一 `(consumer, execution_id, event_id)`；outbox 用 idempotency_key、状态与重试次数。
投影幂等键为 `(execution_id, manifest.revision, entity_kind, entity_id)`，同键不同 digest 为冲突；过旧 revision 不覆盖新值。
提交顺序：输入独占落盘→平台 binding / outbox 事务→worker 领取→内核写产物 / manifest→平台读清单核验→事务投影→确认消费。
内核完成、投影失败时标记 projection_pending / failed；只重放投影，不重跑模型。下一步验证调度是平台独立 outbox 意图。
不承诺外部调用恰好一次：call_id / attempt / 请求摘要 / 已知结果必须入账；领取租约、版本比较与去重降低重复，未知结果不得猜测。

## 10. 错误、版本与最小跨模块交接样例

错误码至少包括 invalid_contract / unsupported_version / unsupported_operation / identity_mismatch / integrity_error /
evidence_invalid / target_not_authorized / approval_required / approval_stale / tool_unavailable / tool_failed / parse_failed /
model_unavailable / model_output_invalid / budget_exhausted / resource_exhausted / cancelled / checkpoint_invalid /
execution_conflict / external_outcome_unknown / internal_error。category 固定为 input / identity / integrity / tool / model / budget / control / internal。
retryable 只是诊断提示，是否新建重试由调用方决定；失败不落成 succeeded + []。
Schema major 不兼容必须拒绝；minor 新字段也需先由 capabilities 声明 reader 支持，再交互，不违反 extra=forbid。
capabilities 返回支持的 contract 版本、module / operation、method 版本、所需资源和运行状态枚举；三种版本互不代替。
桥接显式版本映射，旧契约 / 旧图由 legacy executor 读取；历史 ORM JSON 不就地转换。

以下是交接顺序示意，引用对象字段按前文定义展开，DEC-002 需提供完整可校验 JSON 样例与 Schema：

```text
discovery.execute(RunSpec[discover], local_context)
  -> DiscoveryResult(candidates_ref, evidence_ref, assessments_ref, coverage)
CLI decide / 平台人工确认
  -> DecisionRecord(candidate EntityRef, snapshot_id, evidence_refs, actor, reason)
  -> 冻结 TargetBundle(candidate / evidence / decision 引用)
repair.execute(RunSpec[generate](TargetBundle, PatchScope, SuiteRef), context)
  -> RepairResult(patch_ref, patched_source, attempts_ref, checks)
repair.execute(RunSpec[verify](repair_ref, patch_ref, SuiteRef), context)
  -> RepairVerifyResult(before / after / suite / patch 身份绑定的 receipt)
rules.execute(RunSpec[generate](TargetBundle, CorpusSnapshot), context)
  -> awaiting_input + RuleResult(draft) + ApprovalRequest
CLI / 平台批准 -> runs.resume(ControlCommand, ApprovalDecision)
  -> RuleResult(technical_validation)；接受 / 发布仍由各自使用方决策
```

独立评分器只接收冻结结果和其专有 oracle，输出独立 evaluation ledger，含输入 / 方法 / 样本 / epoch 身份。
执行账本不承载论文分数；平台展示研究导入包也不把评价标签混入下一轮模型上下文。

## 11. 对应接口的语义注释（实施中）

约束位于具体声明与发送 / 接收代码，不新增 AGENTS.md 规则。普通 JSON 不含注释；JSON Schema 使用 `$comment`、`x-semflow-contract`、`x-semflow-schema-version` 和 `x-semflow-semantics-revision`。`semflow_contracts.wire.MEANINGS` 保存稳定 ID，capabilities 暴露语义修订，标记检查拒绝未知 ID 或缺少任一端的注释。

| 契约 ID | 声明 / 发送端 | 接收端及不可变语义 |
| --- | --- | --- |
| research.run | RunBase；CLI dispatch | validate_spec / factory.policy_for：科研身份、显式冻结值，不推断平台 ID |
| research.result | ResultEnvelope；runtime.execution.execute | LocalLedger.publish / inspect：完成、覆盖、技术检验和人工接受相互独立 |
| research.manifest | ResultManifest；LocalLedger.publish | LocalLedger.inspect：精确 spec / result 字节、revision 与事件序列 |
| research.evidence | EvidenceRecord；SnapshotReader.read | SnapshotReader.validate / bundle_io.import_targets：同快照原文件摘要、真实逻辑行片段、授权上游 |
| research.event | ExecutionEvent；LocalLedger._append | LocalLedger.events：每执行单调序列，重投递不改变观察身份 |
| research.approval | ApprovalRequest / Decision；public.actions.approve | approvals.validate_approval：同 action、完整主体引用、检查点和显式人工动作；不是技术通过 |
| research.control | ControlCommand；CLI dispatch | LocalControl.request_cancel / validate_resume：取消仅请求，恢复绑定执行和修订 |
| research.checkpoint | CheckpointBundle；DurableSaver._persist | DurableSaver.restore：固定原生引擎、输入摘要和单执行线程，不改写历史图 |
| research.model_exchange | modelio.StrictModel；CompatibleModel.generate | 同方法的 schema receiver / frozen_call：先结构后证据，未知调用不自动重放 |
| research.source | SourceManifest；sources.capture | sources.materialize：规范清单摘要、完整归档成员、精确原字节 |
| research.bundle | Candidate / Evidence / Decision / Assessment / StaticFinding Bundle；commit_bundle | load_bundle / import_targets：生产者、快照、成员与类型一致，子引用须验证 |
| research.resources | ToolSettings 序列化 / factory.assemble | 同 factory 的重启校验：排除凭据，拒绝变更 endpoint / 工具 / 镜像 / 限额 |

发送端与接收端注释明确要求 Agent 同时检查另一端、类型声明和兼容性测试；不得仅改一端的字段名、默认值、状态、ID、摘要算法或批准主体。新平台 bridge 落地时必须增加其实际发送 / 接收位置，不用尚不存在的模块作为已完成证据。

当前草案的 run / result / evidence / approval 语义修订为 2，其他为 1。新增字段包括每调用 output_tokens、候选原假设 context 和结果 resources_snapshot；未声称旧 reader 能接受新增字段，也未就地改写旧收据。正式切换前仍需版本协商和兼容矩阵验收。

源文件摘要覆盖原始字节；源码片段是 UTF-8 解码后按逻辑行截取、以 LF 连接且无末尾换行，不能将其片段摘要当原文件摘要。源码树摘要是规范 SourceManifest JSON 的 SHA-256，旧平台的 path-NUL-digest 算法须通过显式核验转换，不能因为两者都是 hex64 就互换。

批准主体摘要固定为“有序、完整 subject_refs 的规范 JSON 摘要”，包含生产者、Schema、路径、产物 ID 和内容摘要；单独 hash 查询文本不足以批准规则及样例。校验器拒绝改变任一主体、检查点、action、执行修订或早于请求的批准。通用校验器通过测试不代表规则公共恢复流程已经接通。

科学 Bundle 版本为 semflow.research.bundle/1。SARIF 原始 hash ID 与协议 UUID 分开保留，UUID 用源码快照命名空间和原始 ID 确定生成；复核不得丢失原始静态引用。候选假设中的 missing / unknown premises 必须保留至复核，模型支持意见不得写成人工 confirmed。

## native 修复桥接预算与结果补充（2026-11-11，run 语义修订 4）

`RepairMethodPolicy.max_candidates` 是补丁候选尝试数，不是目标数；可选 `model_call_limit` 是独立于总 execution 预算的修复模型调用上限，progress 模式也执行。`InspectionLimits.max_steps` 是总源码工具额度，`initial_source_steps` 是其中初始理解可用额度，必须小于等于总额。缺省 None 保留旧请求映射；新平台桥接必须显式传入冻结值。`factory.policy_for` 和对应声明/发送端注释共同约束，不能把初始额度扩大为总额。

平台冻结确认输入的 producer 为 `uuid5(execution_id, "repair-inputs/1")`；候选/决策 ID 在该 namespace 内按平台原 ID 派生，结果通过显式映射回平台。源快照旧 hash 和科研 canonical manifest hash 先验证再转换。原始证据摘录 hash 与行范围需与源码一致；确认仍绑定原证据，不自动补一个新窗口替代失效依据。

`public.repair_results` 从已发布清单读取 selected attempt、proposal、patch、source、原始命名检查；平台投影保留 typed checks 和原始收据，未执行的 project tests/rescan 明确 not_run。公开字节 hash 不等于历史 native JSON/context 私有 hash。无产物 failed/cancelled/interrupted 合法且不创建 RepairRecord；技术 checks_passed 不是 accepted。已提交投影可重建丢失展示文件，但已有变动内容应报错，不能静默覆盖。

## S1 suite / rescan / comparison 补充（2026-11-12）

`FrozenSuite` 保存完整可执行断言、目标引用、源码摘要、固定验证镜像和原始定义来源；生成或导入都先冻结，执行端只读取 `SuiteRef` 与不可变文件。目标重新映射必须携带原始 suite 引用和逐目标别名，并由接收端再次核对候选身份、位置、弱点和证据；平台用户确认不进入科研判断。

`RepairValidationPlan.static_baseline` 与 `rescan` 成对出现。baseline 包含实际 CodeQL DB、SARIF、版本、查询包、suite、补充规则和源码身份；复扫使用相同工具/查询输入，工具失败、SARIF 解析失败、仍命中和清空分别表达，清空不能单独证明修复。原始 JUnit XML、控制台输出和 SARIF 都提交为 ArtifactRef，删除工作目录后仍可核验。

`RepairVerifySpec` 是无模型、无 Prompt 的独立技术操作；重复 before/after 结果只覆盖冻结 suite 的测试范围。project tests、syntax、rescan 和 before_after 是独立检查，平台接受仍需最新人工确认和接受事务。平台旧 DTO 的 hash/ID 由 `repair_check_views` 明确转换，科研身份作为旁证保留，不以同形字符串互换。

## S2 OpenHands 补充（2026-11-12）

`OpenHandsPolicy` 冻结 SDK `1.56.0`、镜像 digest、模型 endpoint profile、Prompt version、最大步数、总超时/停滞时限、输出预算、依赖环境和开发命令；它位于 `RepairGenerateInput`。`repair_openhands` 只读取 `RunSpec.prompts` 中 `repair_openhands` 角色的冻结引用，不重新加载安装目录模板。`openhands_resources` 把 `image_digest / endpoint_profile / timeout_seconds` 显式转为 worker 的镜像、实际 URL 与时限。资源快照保存四个 worker 文件的字节摘要，启动和恢复拒绝变化。核心资源缺失返回 `tool_unavailable`；平台尚未装配请求时仍可返回平台的 `resource_unavailable`，不转为 native。

`OpenHandsReceipt`（`research.openhands_receipt` / `semflow.openhands-receipt/1`）绑定 execution、policy digest、worker status/error 和成员引用。成员包含实际 runtime 结果、事件、脱敏控制台、工具/预算握手收据、清理结果和部分 workspace ZIP。成功尝试使用 `AttemptRecord.engine_receipt`；失败、超时、取消或后续检查抛错时由 `Failure.detail` 及结果的 artifacts 保留。读端验证全部成员字节，删除工作目录仍可复核。旧 `semflow.openhands-usage/1` 仅按历史 usage 读取，不升级为完整 worker 证据。

SDK 每次生成前通过本地握手请求已有 `CallJournal` 的持久预留，结束后确认实际 tokens；全局及方法调用上限包含语义与 SDK 两类调用。worker 损失、取消或未知响应保留占用且不自动重放，Usage 按模型/来源分组，不把未知用量写成零。父进程执行总预算、worker 时限和停滞时限，取消停止所属进程组与专属容器。worker 完成只表示交付候选，仍需已观察窗口/可写范围/文件数检查、独立技术检查和平台人工接受。

CLI 的 `repair-openhands` 由上游结果、候选选择、明确确认、科研 options 和 resources 装配同一 RepairSpec；高级 RunSpec 入口保留。Web 冻结模型/资源/身份并投影，均调用 `repair.execute`。run 语义修订 6、resources 修订 2、repair_attempts 修订 2；普通 JSON 不加入注释，约束写在类型/Schema 及真实发送接收端，AGENTS.md 不增加规则。

</details>
