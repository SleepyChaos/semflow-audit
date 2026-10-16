# RealVuln 六组消融：冻结与执行协议

2026-10-14。用户要求按交接报告补全信息，并明确授权执行 D/E 独立复审及六组消融。Vul4Py、CQLLM 和端到端修复暂缓；没有遗留 Vul4Py 进程。本批数据已用于开发调优，属于配对机制分析，不是新的独立盲测。

## 输入和版本

全量范围固定 26 项目、676 条漏洞、120 个陷阱。来源为作者GitHub历史中的论文兼容提交55350cdc0f0f7db85d1f0b97649df07e6d63c665，记录的v1标签提交为d98e9fc91273702c9547663b6906d1fc494d4fcc；manifest摘要18674aadf29c654d103b136fffb0f3a5e4432dbc43817ac81a652a1f13f4cd9e。当时HF不可用，exact_huggingface_identity_verified=false，不能声明HF v1.0.0逐字节一致。源码按原获取回执重新计算摘要；金标、评分器及实现按冻结哈希核验。原项目级选择保持 20 个 v2、1 个 v3 首次补测、5 个 v3 网络恢复。完整清单在 `artifacts/research/realvuln/20261014-ablation/stage-inventory.csv`。

CodeQL CLI 2.23.5，`codeql/python-queries@1.6.0`，`codeql-suites/python-code-scanning.qls`。成功基线复用，不新增扫描。另记录当前安装查询包845个QL/配置文件及套件摘要（codeql-current-pack-identity.json）；这只能核验当前包，不补造旧扫描时未保存的包字节摘要。上游 Scout7 的已持久化候选、引用和原始假设复用，不重新调查或按金标筛选。网络恢复的候选继承关系和阶段用量分别保留。

生产代码冻结为 `20261013-progress-v3-retest` 的201个源码/提示文件。v2 与 v3 只在 `app/adapters/ai/policy.py` 有差异；修正 rejected_assessments 被误算为停滞的逻辑属于复审调度差异，不把20个v2复审包装成统一v3结果。正式 F 复用6个已有v3复审，补跑其余20个。

模型请求 `deepseek-v4.1-flash`，已有真实响应 `deepseek-v4-1-flash-260910`；新增运行继续记录实际响应，供应商标识漂移须单列。Review12 提示摘要 `50d48adf1ff39d1bc153adb68babb207a1488d458714acf26f8edb0ec9c5ded8`；Scout7 摘要 `970c120e7b8135d734d5969e11c5866acaf76afb8d3b795cd04589a96c919a14`。

复审三组使用相同默认 ReviewRequest：全部候选、允许证据工具、8步局部取证、40000字符上下文、批次4、max_batches=0；仅调整候选来源组合。阶段总调用/token/时间限额为0，单次请求90秒、恢复1次、无进展保护3；语义策略40000字符／8次工具／修复尝试3显式固定。最后一项是共享配置身份，不在本轮执行修复。

## 六组与隔离

| 组别 | 输入／处理 | 新执行范围 |
|---|---|---|
| A | CodeQL原告警，多CWE展开，与官方评分规则一致 | 0，核验后复用26项目 |
| B | Scout结构与引用验证后候选，不做Review | 0，独立重评分26项目 |
| C | A＋B原始并集，CodeQL在先，Scout在后 | 0，重评分26项目 |
| D | 仅CodeQL候选进入Review12 | 26个独立复审 |
| E | 仅Scout候选进入Review12 | 26个独立复审 |
| F | CodeQL＋Scout进入Review12 | 20个统一v3复审，6个v3复用 |

D/E/新增F创建独立 audit ID 和候选池；保留不可变源码与CodeQL数据库引用。E的`findings=[]`表示实验明确不选择CodeQL输入，基线实际成功回执仍保留，不表示扫描得到零告警。D不导入Scout阶段。E/F仅导入冻结Scout候选、其原始假设和校验过摘要/审计/快照身份的证据，重建本组候选及证据ID。原复审答案、分类和人工决定不导入；新候选均从pending开始。

所有组允许相同完整源码、原项目公共说明及生产只读取证工具；Review的static_query工具权限不因组别改变。组别区别在上游候选池，不宣称E内部完全禁用CodeQL工具。金标、旧Review答案、竞品输出只用于离线评分，不能作为模型输入或生产检索资料。模型上下文受 EvidenceService 项目根和证据身份校验约束。另保存437条可读公共知识块的版本、摘要及来源清单（knowledge-inventory.json）；历史采用F的实际工具轨迹只有read_source262次、search_source21次，没有knowledge/static_query调用。新增阶段继续按实际轨迹报告，不把允许读取等同于确实使用。

## 评分与交集

继续使用冻结官方 matcher：相同相对文件或 acceptable_locations、acceptable_cwes、行区间±10，优先漏洞、每个金标只消耗一次。unknown CWE保留为FP，未评估不伪装成功零告警。原始候选与多CWE展开后的评分条目数量分列，没有新增语义去重规则。CSV原precision/recall/f1/f3字段为0–1比例，同时提供对应*_100列；Markdown中的Precision/Recall为百分数、F1/F3为0–100，避免混淆量纲。

已发现顺序分配歧义：独立A/B的已分配金标并集415条，C合流416条；PyGoat的 `pygoat-053` 为C新增分配。`discovery-overlap.csv`同时提供独立命中、C命中及每路所有兼容候选。独立集合：A独有26、B独有309、共同80、共同遗漏261。C一致条件分解为CodeQL兼容独有25、Scout兼容独有309、共同兼容82、C遗漏260；这是C已分配标签上的兼容来源，不能冒充独立A/B评分TP。全部兼容标签441也不能当作C的416条正式TP。

逐候选去向必须引用池ID、来源、证据、原始与复审后CWE/位置、评分分配及全部兼容金标；另按金标提供 retained/lost/gained/missed，候选数不代替漏洞数。历史F的拆分属于来源分析，D/E另跑，不能由F答案推导独立成绩。

## 资源、停止与交付

逐请求账本记录新执行和复用，按阶段ID去重；继承候选所需的历史Scout阶段计入采用成本。A/B/C/F共享的发现阶段不能将各行相加当作累计成本。全部尝试包含本次及20261013初始、v2、首次v3与恢复阶段，包括失败；缺失usage和响应ID分别标未知。计时为实际阶段回执之和与静态回执时间，不能称GUI并发延迟。

供应商限流、超时或连接异常停止继续派发付费阶段，保留既有回执和阶段ID；恢复不得择优覆盖旧结果。局部证据不全仍为未决。同池恢复使用原阶段ID与持久化批次继续，保留原请求前缀和中断回执；若输入或策略需要变化，创建新阶段并登记原因和全部成本。

输出位于 `artifacts/research/realvuln/20261014-ablation`。`ablation-summary.csv`、`ablation-per-project.csv`固定六组及26项目范围；未执行D/E保持空指标而非零。`discovery-overlap.csv`、`review-transitions.csv`、`review-gold-transitions.csv`、`stage-inventory.csv`、完整阶段账本与结果说明提供追溯。正式结果与历史增量结果另表；全组终态后才标记完整六组消融完成。仅单次运行，差异称本轮观察，不称统计显著。

## 运行中的连接恢复记录

E组PyGoat第102次调用发生APIConnectionError，停止后用一次8输出token上限的真实推理探针验证连接恢复（用量单独记录）。保存原review/result/input回执及阶段状态到attempts/provider-interruption-1/E/realvuln-pygoat；不变更输入、池和候选ID，按原生产图续跑同一StageRun。已有批次按持久化ID跳过，未决由原生产恢复策略处理；调用前缀必须逐字段相同，累计调用与实际两段计时保留，不将阶段恢复包装成额外独立样本。

### 账户限制导致的进程中断

E PythonSSTI原阶段c0ee1519-9733-4c18-b814-777c9af54245在候选池准备后进程退出，数据库无持久化调用或批次。复用原池和阶段恢复，2次调用完成；恢复前状态保存在attempts/process-interruption-1。原片段耗时未知，无法排除未返回回执的在途调用；表中显式标记此成本缺口，已知调用账本不等于供应商账单精确总额。

### F组后半段调度调整

用户询问长时间耗时后，D/E及F前7项目保持原串行记录；F剩余项目分成两条互不重叠队列，总并发最多2，各项目内部仍按原生产图顺序运行。secondary-queue.json预登记ThreatByte至Tornado共7项的独立审计与阶段ID，预写检查点标记。原队列若追上尚未完成的预留项目，由已有标记守卫停止派发，属于调度交接，不重复创建模型阶段；全部新阶段完成后仅补齐6个历史复用回执。配置、提示、候选池、预算和无进展规则不变。操作计时仍分别累加，不把并发墙钟减少当成模型能力提升；此运行调度变化作为偏差说明。
