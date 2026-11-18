# 证据感知增量复审技术设计

## 工作流

CodeQL 和 Scout 保留独立的发现入口、来源与覆盖记录。CodeQL 的告警及路径、Scout 的源码候选经现有合流和产物校验进入 Review。首轮继续使用项目上下文、源码导航、同批次补证及遗漏候选恢复。对照用例可以关闭同批次的可选补证，以便覆盖跨执行恢复，平台的首轮默认行为由原有策略决定。

每次 Review 对已经冻结的候选生成逐候选记录。对待定或未评估项，执行轨迹给出停因、已读范围以及可用的动作。快照内有可读的新位置时，续审先加载指定候选和旧引用，再按预先核验的计划读取新位置，最后调用同一个 Review 内核。旧引用没有覆盖目标、补证计划重复、快照变化、缺外部材料或需人工定位时，内核拒绝该续审。单纯执行故障可走 `retry_execution`。任务和产物用新执行 ID 标识，原报告保持不可变。

| 记录 | 字段与读写路径 |
| --- | --- |
| `CandidateReviewReport` | `DiscoveryResult.candidate_reviews` 引用的可选产物，包括执行、快照、摘要和逐候选条目。保存于现有内容寻址存储。 |
| `CandidateReviewAttempt` | 含候选引用、原候选引用、来源、源码位置、弱点、执行状态、独立的模型判断、证据状态、停因、前提、引用和下一动作。 |
| `ReviewPremise` | 记录角色、状态、理由、政策依据、引文和证据引用。验证层级包括 `source_grounded`、`model_inference` 和 `unresolved`。 |
| `ReviewMemoryIdentity` | 冻结项目快照 UUID 和树摘要、候选与安全属性及可读范围摘要、方法版本和实现及依赖锁与 Prompt/模型摘要、源码门版本。复用范围限于原候选。 |
| `ReviewCacheReceipt` | 保存在 `analysis_trace.state.review_continuation.cache`。记录前后身份、前后源码证据 ID、位置、内容摘要、引用复用或重读、源码和前提命中数及未命中原因。 |

## 校验与状态转换

- 执行状态包括 `not_scheduled`、`not_run`、`completed`、`partial`、`failed`、`interrupted`。证据状态包括未评估、引用通过、未决和校验失败。执行完成仍可返回 `insufficient`，并给出未决前提。
- 引用恢复沿用 `bundle_io` 的快照归属、范围和内容校验。同一快照的已核对源码页可在分析器变更后复用。启用无缓存对照时，按相同位置从快照重新读取。
- 只有既有引用门验收且带确切引文的前提可进入事实层。身份不匹配或证据引用无法重新绑定时，前提不会提供给新执行。前提事实的验证深度限于源码引用和引文。跨过程传播、路径可行性和运行环境前提需要各自的证据。
- 模型收到本轮新证据、可复用旧引用和未决前提后，输出由当前 Review 的结构及证据门再次校验。模型结论和人工确认是独立字段。原候选和新候选通过 `derived_from` 和执行 `retry_of` 回查。
- 公共读取校验报告和候选、判断、证据产物的引用关系。旧回执可省略报告和缓存。平台继续用原续审路由，通过桥接映射科研 ID，通过工作台展示复用源码和已核对引文前提的数量。CLI 和平台共享 `research.public`，无需新增数据库表。

## 可重复对照

冻结同一源码快照、分析版本、Prompt、模型、资源、预算和锁文件。用默认的 `discovery-review` 产出首轮，再对同一未决候选分别执行重读和缓存续审，并保存独立回执。

```powershell
semflow-research discovery-review --root $EvidenceRoot --upstream-execution-id $DiscoveryID --options $ReviewOptions --resources $Resources --dependency-lock $Lock
semflow-research discovery-review-continue --root $EvidenceRoot --upstream-execution-id $FirstReviewID --candidate-id $FirstCandidateID --resources $Resources --dependency-lock $Lock --without-cache
semflow-research discovery-review-continue --root $EvidenceRoot --upstream-execution-id $FirstReviewID --candidate-id $FirstCandidateID --resources $Resources --dependency-lock $Lock
semflow-research discovery-review-report --root $EvidenceRoot --execution-id $NewReviewID --candidate-id $NewCandidateID
```

首轮和二轮的候选 ID 都取自各自的科研结果。CLI 可在未启用平台包和服务的环境运行。对照收据报告缓存命中和未命中，历史条目提供判断变化和停因；原分析轨迹记录调用及 token。真实项目的成本和精度对照需另行执行，计费使用供应商价格和实际计量，标签只在评分时使用。
