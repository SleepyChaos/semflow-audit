# 已收集测试结果：分类、用途与版本

整理日期：2026-10-10。按[三级分类 v2](classification-draft-v2.md)将主要历史测试系列落位。本文有 **28 条分类记录，涉及 23 份结果/诊断报告**；报告跨功能关联，条目数不等于独立实验数或通过数。候选材料另查v2的32项材料表。

分类路径为 **功能 → 测试意图 → 测试材料类型**。项目改进版本是查询结果的另一维度：同类测试可跨版本，同一改进版本也可同时验证三类功能。文档v2、项目IMPROVE编号、Prompt版本、运行批次和归档批次各自独立。

本表引用冻结批次 `20261009-workspace-v3`，版本归属逐项来自其[机器登记册](../../docs/testing/20261009-workspace-v3/registry.json)。`VALIDATION-10-*` 是IMPROVE-10的补充验证分组，不能当作新的产品改进。多版本/旧版对照报告保持各分项实际实现身份，不以整份报告的归档组替换。

精确结果ID、完整SHA-256、版本收据及原执行位置见[配套分类索引](collected-results-classification.json)。引用冻结副本时使用归档ID＋结果ID＋SHA-256，并按原登记册定位本地副本；下列报告链接方便阅读工作区原件，不保证后续字节不变。

## 一、双引擎代码审计

| 分类标识 | 测试意图 → 材料类型 | 已收集测试/结果入口 | 改进归档组 | 用途与状态 |
| --- | --- | --- | --- | --- |
| AUD-01 | 1.1 审计准确性 → 专项测试集测试 | [六个双引擎开发样例](../../docs/research/dual-engine-development-results.md) | `IMPROVE-06` | 自建开发集；多轮入口调整与失败保留，作为开发/回归。 |
| AUD-02 | 1.1 审计准确性 → 项目测试 | [首轮项目校准](../../benchmark-data/experiments/calibration-results.md) | `IMPROVE-06` | 正式准入未完成；复核、修复与规则部分分别阅读。 |
| AUD-03 | 1.3 告警复核与误报控制 → 项目测试 | [RealVuln候选池匹配复测](../../benchmark-data/experiments/discovery-retest-results.md) | `IMPROVE-07` | 复用静态结果与候选池；新Scout单列，属于开发复测。 |
| AUD-04 | 1.4 检查覆盖与失败处理 → 项目测试 | [RealVuln窗口/输入覆盖整改](../../benchmark-data/experiments/discovery-coverage-results.md) | `IMPROVE-08` | 多轮补读组合；检查范围与准确性分开，不称单轮独立验收。 |
| AUD-05 | 1.2 业务语义、跨文件取证与定位 → 项目测试 | [RealVuln语义整改](../../benchmark-data/experiments/discovery-semantic-results.md) | `IMPROVE-09` | 累计29/31为组合结果；样本已暴露，供回归。 |
| AUD-06 | 1.2 业务语义、跨文件取证与定位 → 专项测试集测试 | [机制变换/泛化回放](../../benchmark-data/experiments/discovery-generality-review.md) | `IMPROVE-09` | 历史样例变换与回放；不能代替新模型端到端项目发现验收。 |
| AUD-07 | 1.1 审计准确性 → 专项测试集测试 | [OWASP56发现试测](../../benchmark-data/experiments/owasp-discovery-results.md) | `IMPROVE-09` | 56例模型与1230例静态的输入范围不同；unknown保留。 |
| AUD-08 | 1.1 审计准确性 → 专项测试集测试 | [OWASP48开发/冻结验收对照](../../benchmark-data/experiments/owasp48-final-comparison.md) | `IMPROVE-10` | 开发与验收、base/revision-01/revision-02分开；已评分样本转回归。 |
| AUD-09 | 1.1 审计准确性 → 专项测试集测试 | [两组新OWASP48，共96文件](../../docs/research/supplemental-20261009-results.md) | `VALIDATION-10-SUPPLEMENT` | 同批静态/Scout/并集/复核分列；已评分、同公开合成分布，非全告警盲审。 |
| AUD-10 | 1.6 审计产品链路 → 工程流程用例测试 | [Py/JS HTTP夹具真实上传/Worker/发现/复核](../../docs/research/chain-completion-20261009-results.md) | `VALIDATION-10-CHAIN-COMPLETION` | 两语言发现/复核完成；修复/规则及最终页面链路未完成。 |
| AUD-11 | 1.4 检查覆盖与失败处理 → 工程流程用例测试 | [首轮校准失败诊断](../../benchmark-data/experiments/failure-analysis.md) | `IMPROVE-06` | 诊断记录；解析失败和未完成门槛不能计为零结果成功。 |
| AUD-12 | 1.1 审计准确性 → 专项测试集测试 | [OWASP上游/本地口径对照](../../benchmark-data/experiments/owasp-upstream-comparison.md) | `IMPROVE-06` | 用途为评分口径核查；与后续OWASP48/96分母分开。 |

## 二、代码修复

| 分类标识 | 测试意图 → 材料类型 | 已收集测试/结果入口 | 改进归档组 | 用途与状态 |
| --- | --- | --- | --- | --- |
| FIX-01 | 2.1 修复正确性与安全有效性 → 专项测试集测试 | [自然JS来源的有界模块oracle校准](../../benchmark-data/experiments/repair-calibration-report.md) | `IMPROVE-06` | 六项目候选逐项准入；模块裁决不代表完整项目修复率，部分后快照仍不安全。 |
| FIX-02 | 2.2 正常功能与业务语义保持 → 专项测试集测试 | [语义修复业务样例](../../docs/research/semantic-development-results.md) | `IMPROVE-04` | 自建/已暴露开发任务；正常功能与安全联合验证。 |
| FIX-03 | 2.1 修复正确性与安全有效性 → 专项测试集测试 | [10纯模块，Py/JS各5个，Repair1/2](../../docs/research/supplemental-20261009-results.md) | `VALIDATION-10-SUPPLEMENT` | Repair1联合10/10；Repair2为9/10及1未评估，20请求只计10独立任务。 |
| FIX-04 | 2.6 接受补丁与产品链路 → 工程流程用例测试 | [HTTP项目实际修复/接受/Diff流程](../../docs/research/chain-completion-20261009-results.md) | `VALIDATION-10-CHAIN-COMPLETION` | 参考补丁与oracle已校准；实际模型修复及后续流程尚未完成。 |

## 三、规则生成

| 分类标识 | 测试意图 → 材料类型 | 已收集测试/结果入口 | 改进归档组 | 用途与状态 |
| --- | --- | --- | --- | --- |
| RULE-01 | 3.4 RAG与执行反馈的贡献 → 专项测试集测试 | [框架/开发反馈/规格等QL消融](../../docs/research/rule-generation-ablation-results.md) | `IMPROVE-03` | 修正前缓存成绩作废；读取修正后收据，同任务对照。 |
| RULE-02 | 3.2 规则检测准确性与安全反例 → 专项测试集测试 | [旧K与语义规则匹配复测](../../docs/research/legacy-rag-matched-results.md) | `IMPROVE-04` | 同任务预算对照；与单案例3/3及后续full_v8成绩分开。 |
| RULE-03 | 3.5 检索与资料约束正确性 → 工程流程用例测试 | [RAG官方语料v3可用性](../../docs/research/rag-corpus-expansion-v3-results.md) | `IMPROVE-05` | 语料/开发测试可用性；不算生成规则的隐藏准确率。 |
| RULE-04 | 3.5 检索与资料约束正确性 → 工程流程用例测试 | [RAG官方语料v4可用性](../../docs/research/rag-corpus-expansion-results.md) | `IMPROVE-05` | 编译、执行和失败排除分开；语料不兼任独立金标。 |
| RULE-05 | 3.1 生成成功率与可执行性 → 专项测试集测试 | [v7/v8六族QL稳定化](../../docs/research/rag-stabilization-results.md) | `IMPROVE-05` | 候选生成与执行验收分开；旧K复用及外部source预算单列。 |
| RULE-06 | 3.2 规则检测准确性与安全反例 → 专项测试集测试 | [语义规则业务样例](../../docs/research/semantic-development-results.md) | `IMPROVE-04` | 与修复共用报告；规则单案例和整套18任务不能混为一项成绩。 |
| RULE-07 | 3.2 规则检测准确性与安全反例 → 专项测试集测试 | [12新文件，历史full_v8的18候选迁移](../../docs/research/supplemental-20261009-results.md) | `VALIDATION-10-SUPPLEMENT` | 15/18候选通过；新模型生成0次，同族重复不算独立漏洞，review_anchor未评估。 |
| RULE-08 | 3.7 批准、发布与规则再用 → 工程流程用例测试 | [两语言生成/批准/发布/新上传再用](../../docs/research/chain-completion-20261009-results.md) | `VALIDATION-10-CHAIN-COMPLETION` | 后续流程尚未完成；不能将准备夹具计为真实发布通过。 |

## 共享流程材料的关联

共享回归按其实际检查的功能关联三大类；主归属便于查找，重复关联不重复累计通过数。补测报告中的GUI、可靠性回归和费用收据也属于共享附件，不混入准确性任务分母。

| 分类标识 | 主路径 | 结果入口 | 改进归档组 | 关联与边界 |
| --- | --- | --- | --- | --- |
| FLOW-01 | 双引擎代码审计 → 1.4 检查覆盖与失败处理 → 工程流程用例测试 | [基础四阶段回归及静态微基准](../../docs/research/benchmark-results.md) | `IMPROVE-00` | 关联修复/规则；静态微基准另属1.1专项测试集，集成替身与真实模型分开。 |
| FLOW-02 | 双引擎代码审计 → 1.6 审计产品链路 → 工程流程用例测试 | [早期真实模型四阶段smoke](../../docs/research/live-model-results.md) | `IMPROVE-00` | 关联修复/规则；30阶段尝试、27完成、3失败，仅验证早期实际模型响应。 |
| FLOW-03 | 双引擎代码审计 → 1.4 检查覆盖与失败处理 → 工程流程用例测试 | [首轮M1/M2/M3回归与集成](../../docs/research/phase-one-test-results.md) | `IMPROVE-01` | 关联修复/规则；按各子实验用途阅读，不作当前默认能力准确率。 |
| FLOW-04 | 双引擎代码审计 → 1.6 审计产品链路 → 工程流程用例测试 | [第二阶段真实项目链路与回归](../../docs/research/phase-two-results.md) | `IMPROVE-02` | 关联修复/规则；排除的集成项不计通过，早期Prompt和今日默认分开。 |

## 后续登记的固定字段

| 字段 | 记录要求 |
| --- | --- |
| 功能、意图、类型 | 使用v2三级结构；一条实际任务明确主用途，跨功能仅关联。 |
| 材料/任务身份 | material_id、task_id、输入快照与标签/评分规则指纹；项目来源不自动等于项目级评测。 |
| 就绪、暴露、执行状态 | 就绪/待补齐/仅参考；开发/回归/待准入；完成/失败/unknown/未评估分别记录。 |
| 项目改进与实际实现 | IMPROVE/验证分组＋Git/工作树内容身份＋各实际Prompt版本；旧对照不重命名为新实现。 |
| 环境与配置 | 当次依赖锁、CLI/pack、容器镜像身份、模型实际响应、预算/seed、RAG与缓存。缺证据保持未知。 |
| 原始结果引用 | 原run_id/阶段ID、归档ID、RES ID、完整SHA-256、版本收据引用；不只写“v8通过”。 |
| 计分与附件 | TP/FP/FN等能力指标与工程通过数分开；作者成绩、复用、诊断、耗时/token各自标注。 |

本次仅整理分类与结果关联，没有新增测试执行，也没有改写历史分数、原始版本收据或不可覆盖归档。
