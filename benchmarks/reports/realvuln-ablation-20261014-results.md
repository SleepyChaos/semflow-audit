# RealVuln 六组消融补全结果

2026-10-14。六组均覆盖固定26项目、676漏洞、120陷阱。A/B/C复用冻结发现输入并独立评分；D/E各26项目独立Review12；F新增20项统一v3复审，复用6项v3结果。上游Scout保留已冻结的增量候选与继承历史，统一的是复审实现，不称全链v3全量重跑。

supported是实际证据门通过的模型判断，不是人工确认或利用成功。FP为未匹配基准标签，未逐项独立验证。所有未决和失败保留。
F3 = 10TP / (10TP + 9FN + FP)，更重视召回。精确率提高不代表F3提高，应同时检查丢失命中和未匹配输出的变化。

| 组别 | 链路 | TP | FP | FN | Precision (%) | Recall (%) | F1 /100 | F3 /100 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | CodeQL | 106 | 297 | 570 | 26.30 | 15.68 | 19.65 | 16.34 |
| B | Scout | 389 | 534 | 287 | 42.15 | 57.54 | 48.66 | 55.52 |
| C | CodeQL＋Scout | 416 | 910 | 260 | 31.37 | 61.54 | 41.56 | 56.14 |
| D | CodeQL＋Review | 110 | 63 | 566 | 63.58 | 16.27 | 25.91 | 17.58 |
| E | Scout＋Review | 311 | 210 | 365 | 59.69 | 46.01 | 51.96 | 47.09 |
| F | CodeQL＋Scout＋Review | 354 | 366 | 322 | 49.17 | 52.37 | 50.72 | 52.03 |

![六组Precision、Recall、F3及TP/FP对照](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/ablation-comparison.png)


## 模块收益与损失

以下为本轮配对观察，每组仅一次运行，不称统计显著或新独立盲测。

| 对照 | TP变化 | FP变化 | Precision百分点 | Recall百分点 | F3变化 |
|---|---:|---:|---:|---:|---:|
| A→C | +310 | +613 | +5.07 | +45.86 | +39.80 |
| B→C | +27 | +376 | -10.77 | +3.99 | +0.62 |
| A→D | +4 | -234 | +37.28 | +0.59 | +1.24 |
| B→E | -78 | -324 | +17.55 | -11.54 | -8.43 |
| C→F | -62 | -544 | +17.79 | -9.17 | -4.11 |
| D→F | +244 | +303 | -14.42 | +36.09 | +34.45 |
| E→F | +43 | +156 | -10.53 | +6.36 | +4.94 |
| A→F | +248 | +69 | +22.86 | +36.69 | +35.69 |

本轮观察：

- 当前完整系统命中354/676，保留CodeQL独立命中的102条，额外匹配252条，仍未保留其中4条。相对CodeQL，FP总数增加69，不能宣称所有指标改善或误报总数下降。
- 发现端：加入Scout后，A→C新增净命中310条，Recall增加45.86个百分点；主要扩展来自Scout独有命中。CodeQL仍保留26条独立独有命中。
- 六组F3最高的是C（CodeQL＋Scout，56.14）；仅比较复审输出，F3最高的是F（52.03），Precision最高的是D（63.58%）。
- 完整链路C→F：TP净变化-62、FP净变化-544、Precision变化+17.79个百分点、Recall变化-9.17个百分点、F3变化-4.11。这说明发现结果和supported输出需要分别评价，未决仍应保留给后续取证。
- 改进应先处理下方未决与证据门拒收原因、提升独立新项目发现覆盖，再验证复审的召回收益；不能仅按FP净减少数量判断Review质量。多CWE收敛与评分分配变化也贡献了分数变化。

## 复审去向

按金标分配和候选状态分别统计，未进入supported不默认排除。多CWE展开、CWE修订及顺序分配变化单独保留。历史F的FP净差551由336条原FP未进入supported与215条supported输出多CWE缩减／重新匹配净变化组成，后者不等于215次语义排除；详细原去向表单独保存。

| 组别 | 原命中保留 | 原命中未保留 | 复审新增匹配 | 前后均遗漏 | 候选状态 |
|---|---:|---:|---:|---:|---|
| D | 104 | 2 | 6 | 564 | {'supported': 165, 'excluded': 2, 'unknown': 3, 'insufficient': 1} |
| E | 311 | 78 | 0 | 287 | {'insufficient': 230, 'supported': 521, 'excluded': 71, 'unknown': 101, 'pending': 1} |
| F | 353 | 63 | 1 | 259 | {'supported': 709, 'insufficient': 264, 'excluded': 78, 'unknown': 43} |

E组计划池923项，最终候选状态合计924项：VulPy复审批次a903960fc19bc235d15756ad保存了1条新的未验证会话伪造线索，候选c9c51f5a-208f-46b1-8720-707e2874e544保持pending，未进入原95项项目候选池。它不是恢复继承的历史pending，不进入supported的TP/FP成绩。


### 原始评分条目进入复审的状态

这些是多CWE展开后的原始TP/FP条目去向，不能与复审最终FP直接相减来计算语义排除。

| 组别 | 原TP条目状态 | 原FP条目状态 | CWE修订候选 | 位置修订候选 |
|---|---|---|---:|---:|
| D | {'supported': 105, 'unknown': 1} | {'supported': 288, 'excluded': 3, 'unknown': 5, 'insufficient': 1} | 17 | 0 |
| E | {'supported': 310, 'insufficient': 46, 'unknown': 29, 'excluded': 4} | {'supported': 211, 'insufficient': 184, 'excluded': 67, 'unknown': 72} | 9 | 0 |
| F | {'supported': 353, 'insufficient': 41, 'unknown': 17, 'excluded': 5} | {'supported': 569, 'insufficient': 235, 'excluded': 77, 'unknown': 29} | 31 | 0 |

FP净变化按两部分核对：

- A→D：9条原FP评分条目未进入supported；仍为supported的原FP条目与最终FP相差+225条。后者包含CWE收敛、去重、重新匹配及新输出变化，不能称为225次语义排除。
- B→E：323条原FP评分条目未进入supported；仍为supported的原FP条目与最终FP相差+1条。后者包含CWE收敛、去重、重新匹配及新输出变化，不能称为1次语义排除。
- C→F：341条原FP评分条目未进入supported；仍为supported的原FP条目与最终FP相差+203条。后者包含CWE收敛、去重、重新匹配及新输出变化，不能称为203次语义排除。

### 未决与实际取证

- D：成功／部分批次记录的工具观察 {'read_source': 44}，其中复用 {'read_source': 2}；停止原因 {}；证据门拒收主要原因（按候选去重，同一候选可涉及多种原因）[('安全属性不一致；不能以认证证据替代角色或对象授权', 10), ('利用用例必须引用已读取项目源码中的实际入口或操作', 1)]。
- E：成功／部分批次记录的工具观察 {'read_source': 292, 'search_source': 22}，其中复用 {'read_source': 5}；停止原因 {'no_progress': 1}；证据门拒收主要原因（按候选去重，同一候选可涉及多种原因）[('前提需要实际源码引用，不能以文档或模型概括代替', 38), ('仅配置缺陷的输入前提可不适用；操作与保护仍须实际引用', 17), ('控制链有未提供的本地源码；先定向取证或保留未决', 13)]。
- F：成功／部分批次记录的工具观察 {'read_source': 321, 'search_source': 23}，其中复用 {'read_source': 8, 'search_source': 2}；停止原因 {}；证据门拒收主要原因（按候选去重，同一候选可涉及多种原因）[('前提需要实际源码引用，不能以文档或模型概括代替', 36), ('仅配置缺陷的输入前提可不适用；操作与保护仍须实际引用', 35), ('控制链有未提供的本地源码；先定向取证或保留未决', 15)]。
已持久化的判断理由、缺失前提、拒收次数和逐项目状态见review-diagnostics.json及review-diagnostics-per-project.csv；未知与未执行均保留。阶段级trace只保留最后上下文，不能当作全阶段工具账本；以上按逐批次trace统计，失败批次可能缺失工具轨迹，分别有D4/E23/F29个incomplete批次未保存trace。这些记录不能证明完整工具执行次数，原模型响应产物另保留。

## 发现交集、版本与资源

独立A/B金标集合：CodeQL独有26、Scout独有309、共同80、共同遗漏261。独立并集415与C的416差1：PyGoat的pygoat-053受官方按顺序、金标一次分配规则影响。C的已分配416个TP按兼容来源分为CodeQL独有25、Scout独有309、共同兼容82，另遗漏260；此兼容分解不能当作独立A/B命中。discovery-overlap.csv保留两种口径和逐候选依据。

实际复审提示摘要及执行政策已逐阶段核验，独立D/E候选池无跨组来源。模型、prompt、CodeQL、评分器、快照与阶段身份见stage-inventory.csv和formal-review-identity.json。公共知识库437块版本/摘要已登记，实际调用轨迹另保留，允许使用不等于确实使用。

本次新增72个复审阶段已知资源：{'calls': 1973, 'input_tokens': 19824675, 'output_tokens': 2456491, 'unknown_usage_calls': 1}。历史全部尝试按阶段ID去重：{'calls': 3614, 'input_tokens': 31989372, 'output_tokens': 3793322, 'unknown_usage_calls': 18}。F复用的6阶段不计新增；E/F共享上游1819次Scout调用，不能跨组相加。unknown_usage_calls表示未知请求，不将缺失usage记为零成本。实际响应模型与未知响应数见身份清单。

历史与本次所有尝试累计：{'calls': 5588, 'input_tokens': 51814055, 'output_tokens': 6249814, 'unknown_usage_calls': 19}。CodeQL历史实际/复用/失败与耗时：{'historical_actual_attempts': 78, 'historical_reuse_receipts': 9, 'historical_failed_attempts': 26, 'historical_actual_seconds_known': 1206.1538489575032, 'unknown_timing_attempts': 0, 'new_ablation_scan_attempts': 0, 'meaning': 'Actual old scan attempts plus query retries; copied receipts and reused extraction not double-counted; sums are operation time, not GUI latency'}。采用阶段、新执行和累计结果同时保存在resources-comparison.json。
累计额外的1次调用、8输入token和1输出token来自E组PyGoat连接恢复探针，已在provider-recovery-probe.json单列。因此3614＋1973＋1＝5588；该探针不计入六组成绩或采用阶段成本。

采用成本包含必要的继承Scout历史和最终选用复审；全部尝试保留失败及未选用版本。review-resources.csv区分新执行/复用及实际秒数，ablation-per-project.csv保留源码发现覆盖、状态和回执；阶段时间之和不代表GUI并发延迟。
账户五小时限制后，E组PythonSSTI复用原阶段和候选池恢复。旧进程退出前没有持久化模型调用回执；该中断片段耗时未知，且无法排除未返回回执的在途请求。资源表明确标记此缺口，已知成本不能视为供应商账单精确总额。恢复过程和中断前数据库状态保存在attempts/process-interruption-1/。

复审阶段状态分布：{'completed': 78}；覆盖状态分布：{'completed': 47, 'partial': 31}。工作流completed不等于所有候选已获结论。

## 结论边界与交付

本实验补齐了Scout独立评分、D/E独立复审、F版本一致性、发现交集、逐候选/金标去向和实际资源。结合上表判断发现范围、精确率收益与召回损失，不能将预算与调度演进单独归因于某个模块。FP的绝对数量与比例须同时看；未决不当作安全。

数据来自作者GitHub论文兼容提交55350cdc0f0f7db85d1f0b97649df07e6d63c665，未完成与HF v1.0.0逐字节核验，不能宣称HF身份完全一致。本批已参与调优，单次结果不能证明新项目泛化或系统独立自动确认能力。竞品沿用此前作者输出重评分，本轮未重新运行。Vul4Py/CQLLM和端到端修复按用户要求暂缓。

本目录包含完整协议、六组总表与156行逐项目表、676行交集、三组逐候选和2028行金标去向（每组676）、阶段与知识身份、资源账本。历史增量352/359结果保存在historical-incremental/，没有冒充正式F。

## 六组采用资源

采用调用含共享上游与必要继承历史，不能将各组相加作为累计花费。新增调用仅指本次复审；静态调用不折算成模型调用。Token为已知回执用量，未知请求及未计时中断片段另列。

| 组别 | 采用模型调用 | 本次新增复审调用 | 复用复审调用 | 已知输入token | 已知输出token | 未知usage请求 |
|---|---:|---:|---:|---:|---:|---:|
| A | 0 | 0 | 0 | 0 | 0 | 0 |
| B | 1819 | 0 | 0 | 15031996 | 1503440 | 3 |
| C | 1819 | 0 | 0 | 15031996 | 1503440 | 3 |
| D | 179 | 179 | 0 | 1731211 | 241856 | 0 |
| E | 2915 | 1096 | 0 | 25968723 | 2784966 | 4 |
| F | 3106 | 698 | 589 | 27847712 | 3135354 | 3 |

### 执行耗时与批次规模

D/E及F前7项目串行，F后半段改为最多两个独立项目同时运行，各项目内部仍按原生产图顺序执行；调度变化已登记到协议和secondary-queue.json，不变更候选池、提示和模型策略。批次4是上限，按相同条件分组后常拆为较小批次；补充取证和结构／证据校验会增加请求。以下耗时为采用阶段操作时间之和，不是端到端GUI延迟，F含6个历史复用阶段。

| 组别 | 计划候选 | 基础批次 | 平均批次大小 | 模型调用区间秒 | 阶段已知秒 |
|---|---:|---:|---:|---:|---:|
| D | 171 | 102 | 1.68 | 1609.4 | 1664.1 |
| E | 923 | 675 | 1.37 | 8890.0 | 9411.4 |
| F | 1094 | 717 | 1.53 | 10718.4 | 11036.4 |

## 可追溯产物

- [冻结协议](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/ablation-protocol.md)
- [六组成绩与资源总表](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/ablation-summary.csv)
- [156行逐项目结果](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/ablation-per-project.csv)
- [676行发现交集](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/discovery-overlap.csv)
- [逐项目发现交集](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/discovery-overlap-per-project.csv)
- [逐候选复审去向](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/review-transitions.csv)
- [2028行金标去向](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/review-gold-transitions.csv)
- [未决和证据门诊断](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/review-diagnostics.json)
- [模型、提示和输入池身份](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/formal-review-identity.json)
- [采用／新增／累计资源](/Users/chaos/Documents/GitHub/semflow-audit/artifacts/research/realvuln/20261014-ablation/resources-comparison.json)
