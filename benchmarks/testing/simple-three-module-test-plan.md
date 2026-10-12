# Semflow Audit 项目测试方案说明

说明版本 2.2    测试方案 v7    编制日期 2026年10月11日

本方案用于验证双引擎代码审计、代码修复和规则生成三个功能项，并确定后续竞品对照测试的对象与功能范围。三个模块各采用一篇基准论文，审计另采用 OWASP 公开测试项目。正式目标覆盖选定论文的完整测试范围，各基准独立评价，论文原报成绩作为参考。

本文依次说明验证目标、各模块的论文与测试集，以及竞品功能范围和模块对照关系。论文原报成绩用于确定比较口径；本项目性能须通过同一批次的实际运行确认。

## 1. 测试功能与验证目标

### 1 需要验证的三个功能项

双引擎代码审计由 CodeQL 静态引擎和 ScoutAgent 分别发现问题，再由 ReviewAgent 统一复核并汇总。测试需要区分发现能力与复核能力：联合发现是否补足单引擎漏检，复核是否降低误报，最终结论是否仍能关联到真实文件、位置和证据。

代码修复由 RepairAgent 根据已确认问题生成可应用的代码补丁，并依据验证反馈进行有限修订。测试需要证明目标漏洞被消除，同时正常功能保持；语法通过、文字解释合理或与参考补丁相似，都不足以单独证明修复成功。

规则生成由 RuleGeneratorAgent 基于检索知识与给定漏洞信息生成可运行的 CodeQL 查询，并依据编译及开发执行反馈进行有限修订。测试需要证明规则能够执行、在漏洞版本命中目标路径，并能区分对应的修复版本。检索作为生成流程的一部分，本方案评价模块整体效果。

**表1 功能项与验证内容**

| 功能项 | 主要验证内容 | 判定依据 |
| --- | --- | --- |
| 双引擎代码审计 | 准确性、漏检与误报、引擎互补、证据定位、耗时成本 | 原始发现、复核决定、目标匹配、逐项目和逐类别得分 |
| 代码修复 | 补丁可应用、安全有效、功能保持、失败处理 | 候选补丁、实际测试结果、联合通过结果和失败原因 |
| 规则生成 | 查询可执行、漏洞命中、修复版区分、规则可复用 | 候选 QL、双版本执行结果、命中路径和规则版本 |

### 2 项目多智能体设计

本项目围绕 CodeQL 审计、AI 复审、修复 Diff 与报告、RAG 生成规则四个阶段，设计按职责分工的多智能体架构。CodeQL 与 ScoutAgent 构成双引擎发现层，ReviewAgent 对两路候选统一取证复核；已确认问题进一步交给 RepairAgent 和 RuleGeneratorAgent，分别形成可验证的补丁与可复用的检测规则。

ScoutAgent 面向源码主动发现问题，不依赖 CodeQL 已有告警作为唯一入口。ReviewAgent 面向候选及关联证据核实漏洞条件，输出支持、排除或证据不足的复核建议。两者分工用于兼顾发现覆盖与结论可靠性；人工确认决定问题是否进入后续修复和规则生成阶段。

**表2 多智能体职责与协作关系**

| 项目角色 | 输入与协作 | 产出与职责边界 |
| --- | --- | --- |
| ScoutAgent | 源码快照、业务上下文和检索工具；与 CodeQL 共同形成候选池 | 带文件位置与源码证据的漏洞候选；承担主动发现 |
| ReviewAgent | CodeQL 与 ScoutAgent 候选；按需补充源码及调用证据 | 复核意见、证据关联与不确定项；承担候选核实，确认由人工完成 |
| RepairAgent | 已确认问题、相关源码和业务约束；接收补丁验证反馈 | 可应用补丁及修订候选；安全性和功能保持由实际测试判定 |
| RuleGeneratorAgent | 已确认漏洞材料、知识检索和 CodeQL 文档；接收查询验证反馈 | 可运行的 CodeQL 检测规则；发布前须通过漏洞版与修复版验证 |

LangGraph 负责阶段衔接、任务状态及有限次数的反馈修订，RAG 为规则生成提供文档和查询知识，CodeQL 与独立验证器提供实际执行结果。各角色通过问题、证据、补丁和规则的持久化记录协作；模型判断与工具验证分别承担语义分析和结果确认。

### 3 测试分类与全量范围

统一按“功能项 → 测试意图 → 测试集类型”分类。项目测试检验完整仓库中的发现能力；专项测试集检验明确漏洞类别、修复任务或规则任务。工程检查补充验证任务隔离、失败状态和结果关联。

**表3 正式测试范围**

| 功能项与材料 | 全量目标 | 用途 |
| --- | --- | --- |
| 审计 RealVuln 论文 v1.0 | 26 个 Python 项目；676 个漏洞标签和 120 个误报陷阱，共 796 项标签；18 个 CWE 家族 | 项目级漏洞发现与误报控制 |
| 审计 OWASP BenchmarkPython 0.1 | 1230 例；452 正例、778 负例；14 个类别 | 专项准确性与类别覆盖 |
| 修复 PatchEval v1 | 1000 项 CVE 任务；其中 230 项执行动态安全及功能测试；Python、JavaScript、Go | 补丁生成、联合修复成功 |
| 规则 QLCoder ICLR 2026 | 176 项 Java CVE；42 类 CWE；漏洞版与修复版配对 | 规则合成的三条件联合成功 |

全量目标以本表为准，OWASP 的正式目标为全部 1230 例。项目测试和专项测试集分别评价，各基准保留独立分母。

## 2. 双引擎代码审计测试

### 1 论文选择与测试集用途

选用 RealVuln 论文 RealVuln: Benchmarking Rule-Based, General-Purpose LLM, and Security-Specialized Scanners on Real-World Code 的 v1 对应基准。[1] 论文在项目级比较规则扫描器、通用模型 Agent 和安全专用扫描器，适合检验双引擎联合发现及复核的收益。其项目以教学和 CTF 漏洞仓库为主，不能等同于生产环境中的真实 CVE 集。

正式范围为论文 v1.0 全部 26 个 Python 项目、676 个漏洞标签和 120 个误报陷阱。项目源码提交、标签与官方评分器必须属于同一论文版本。后续扩大的 RealVuln 发行版另行建组，不能替换本轮分母后继续引用 v1 成绩。

另使用 OWASP BenchmarkPython 0.1 全部 1230 例进行专项验证。[2] 452 个正例用于观察漏检，778 个负例用于观察误报，14 个类别分别统计。保留完整源码及必要辅助文件，不把单例抽取后的运行条件与完整项目混用。

### 2 论文对照与评价指标

**表4 RealVuln 作者报告的 v1 全量主表成绩**

| 作者配置 | P | R | F1 | F3 |
| --- | --- | --- | --- | --- |
| Kolega.Dev v0.0.1 | 38.8% | 80.9% | 52.4 | 73.0 |
| Claude Sonnet 4.6 Agent | 78.5% | 49.8% | 60.9 | 51.7 |
| Semgrep 默认配置 | 20.5% | 17.5% | 18.9 | 17.7 |

来源为论文第10页 Table 4，F1 和 F3 为百分制。[1] Claude 和 Semgrep 的项目完成数分别为 23/26、25/26，须保留执行失败信息。论文未报告 CodeQL 成绩，CodeQL 对照由本轮实际运行取得。作者模型、规则集或预算与本项目不一致时，原报成绩仅作背景参考。

P 表示报告中匹配目标问题的比例，R 表示已标注漏洞被发现的比例，F1 综合两者，F3 更重视召回。除主表外，报告两个引擎各自独有的有效发现、ReviewAgent 的保留与剔除结果、各 CWE 表现，以及项目执行完成率。

### 3 预期效果与完成条件

合理预期是双引擎较单引擎增加有效漏洞覆盖，ReviewAgent 减少误报且不过度删除正确发现。以同批次 P、R、F1、F3 和逐类结果判断收益，不承诺复用历史小集分数，也不预设超过作者最优配置。

26 个项目及 796 项标签、OWASP 1230 例均须纳入测试目标，提供逐项目、逐例和逐类别的准确性结果。缺少源码、类别或只完成部分样本时，不能标记本模块全量测试完成。

## 3. 代码修复测试

### 1 论文选择与测试集用途

选用 2025 年论文 PatchEval: A New Benchmark for Evaluating LLMs on Patching Real-World Vulnerabilities 及其 v1 测试协议。[3] 该基准从真实 CVE 修复中整理任务，通过安全攻击测试和功能回归测试检查补丁，能够验证“漏洞修好且正常功能保持”，比补丁文字评价或相似度更接近本模块的目标。

正式范围为全部 1000 项 CVE 任务，覆盖 Python、JavaScript、Go 和 65 类 CWE。其中 230 项具有动态沙箱、安全 PoC 与功能测试，作为联合修复成功率的主评测；其余任务仍须生成补丁并按作者等价性协议评价。两种结果分别报告。

### 2 论文对照与评价指标

**表5 PatchEval 作者给定漏洞位置的单次动态修复成绩**

| 作者配置 | 安全与功能联合通过 | 联合通过率 |
| --- | --- | --- |
| GPT-4.1 | 43/230 | 18.70% |
| Gemini 2.5 Pro | 52/230 | 22.61% |
| DeepSeek R1 | 44/230 | 19.13% |
| SWE-Agent 加 Gemini 2.5 Pro | 53/230 | 23.04% |

来源为论文第9页 Table 3。[3] 这些成绩对应特定模型、输入和执行设置。单次补丁成绩与多候选成绩属于不同口径，应分别解释。

主指标为安全与功能联合通过数除以 230。辅助报告补丁生成率、可应用率、安全通过率、功能通过率、1000 项等价性结果、语言和 CWE 差异，以及耗时成本。无补丁、应用失败、安全失败、功能失败和环境未评估分别记录。

### 3 预期效果与完成条件

合理预期是 RepairAgent 较同模型直接修复提高联合通过率，降低破坏正常功能的补丁比例，并能够解释失败原因。结果必须通过实际测试支持，不以语法通过、自建小例通过或参考补丁相似度替代真实 CVE 验证。

完成条件为全部 1000 项任务具有补丁生成与等价性评价记录，全部 230 项动态任务具有安全和功能联合评价记录，Python、JavaScript、Go 三种语言均在范围内。未生成补丁等真实失败保留为测试结果，未执行任务不计为完成。

## 4. 规则生成测试

### 1 论文选择与测试集用途

选用 ICLR 2026 正式论文 QLCoder: A Query Synthesizer for Static Analysis of Security Vulnerabilities，作为本模块唯一论文基准。[4] QLCoder 使用编码 Agent、文档检索、语法与程序结构信息、查询执行反馈来合成 CodeQL 查询；论文采用 Claude Code Agent。它能够直接对应本项目 RuleGeneratorAgent 的规则生成与验证流程。

正式范围为全部 176 项 Java CVE 配对任务，覆盖 42 类 CWE，其中 111 项旧 CVE、65 项为 2025 年新增 CVE。任务包含 CVE 描述、漏洞版本、修复版本和安全修复差异；正式论文的 176 项完整任务是测试目标。

本方案验证给定 CVE 的规则合成效果。检索属于当前模块的组成部分，整体成功率不能单独证明 RAG 的贡献；跨项目泛化另作工程检查。

### 2 成功标准与论文对照

**表6 规则生成成功标准**

| 检查项 | 成功判定 |
| --- | --- |
| 可执行 | 同一 QL 在两版本数据库上编译和运行完成，无执行错误 |
| 漏洞命中 | 漏洞版本至少一条目标路径经过安全修复区域，按作者映射匹配 |
| 修复版区分 | 修复版不再报告经过对应修复区域的同一漏洞路径 |
| 联合成功 | 同一候选同时满足以上三项，完整分母为 176 |

修复版区分不要求整个项目全部告警为空。作者路径精确率按修复区域相交计算，不能等同于所有告警均经独立人工裁决；其他路径和疑似误报另行记录。

**表7 QLCoder 正式论文全量合成成绩**

| 作者配置 | 联合成功 | 成功率 | 平均路径精确率 |
| --- | --- | --- | --- |
| Claude Code Agent 加 Claude Sonnet 4 | 94/176 | 53.4% | 0.631 |

来源为正式论文第8页 Table 1，最多 10 轮。[4] 第9页 Table 4 的 20 项消融中，完整 QLCoder 为 55%，去文档和参考查询为 20%，仅 Claude Code 为 10%。这些成绩仅作方法参考；Table 2 的 130 项共享集也保留独立分母。

### 3 预期效果与完成条件

合理预期是 RuleGeneratorAgent 较同模型基础生成提高三条件联合成功率，减少无效 API 和修复版本误报。辅助报告可执行率、漏洞命中率、修复版区分率、各 CWE 表现、迭代次数、耗时与成本。只有任务、输入、评分和预算一致时才计算与作者的差值，不预设必须超过 53.4%。

完成条件为全部 176 项任务具有真实生成及配对验证结果，覆盖全部 42 类 CWE，每项有候选 QL 或真实生成失败记录。规则的可执行性、漏洞命中和修复版区分分别明确，完整目标不以消融子集替代。

## 5. 竞品功能范围与模块对照

### 1 竞品范围与材料依据

现有竞品文件夹提供了 RepoAudit、QLPro、Antiproof 和 OpenAnt 的研究线索，可用于选择审计及规则生成方向的对照对象。[5–10] 本章依据原始论文与官方项目说明拆解功能，并补充 CodeQL、Semgrep、Alibaba OpenCodeReview 和 Copilot Autofix 等可接入的工具与产品。规则生成仍以 QLCoder 为唯一正式论文基准，扩展候选不增加三个模块的正式基准论文数量。

比较对象按公开入口区分。CodeQL CLI 和 Semgrep CE 是静态工具；GitHub CodeQL 加 Copilot Autofix、Semgrep 平台则包含 AI 功能。研究原型的覆盖范围以论文和公开实现为准，不能将研究能力直接当作可立即接入的产品能力。公开资料核对日期为 2026年10月11日。

### 2 项目与竞品的功能范围对比

表中每行为一个项目或明确的产品组合，每列为本项目对应的能力。“有”表示所列范围提供该能力；“部分”表示能力有限或采用不同形式；“未列”表示所核对的公开材料未列出对应功能，仍需实测确认。代码补丁指可应用的源码修改，检测规则生成指自动生成可执行检测器。

**表8 项目与竞品功能范围对比**

| 项目 | 静态检测 | AI发现 | 证据复核 | 代码补丁 | 修复验证 | 规则生成 |
| --- | --- | --- | --- | --- | --- | --- |
| Semflow Audit | 有<br>CodeQL | 有<br>主动发现 | 有<br>取证复核 | 有<br>源码补丁 | 部分<br>测试、复扫 | 有<br>QL 查询 |
| CodeQL CLI [15] | 有<br>QL 查询 | 未列 | 部分<br>数据流路径 | 未列 | 未列 | 未列<br>手写查询 |
| Semgrep CE [11,16] | 有<br>规则扫描 | 未列 | 部分<br>匹配路径 | 部分<br>规则替换 | 未列 | 未列<br>手写规则 |
| OpenCodeReview [12] | 未列<br>审查规则 | 有<br>审查 Agent | 有<br>定位反思 | 未列 | 未列 | 未列 |
| CodeQL＋Copilot<br>Autofix [13] | 有<br>CodeQL | 未列 | 部分<br>告警上下文 | 有<br>AI 补丁 | 部分<br>复扫、测试 | 未列 |
| Semgrep 平台<br>AI 组合 [14,17] | 有<br>Pro 引擎 | 有<br>Agent 工作流 | 有<br>Assistant | 有<br>Autofix | 部分<br>升级分析 | 未列 |
| RepoAudit [7] | 部分<br>语法分析 | 有<br>数据流发现 | 有<br>数据流验证 | 未列 | 未列 | 未列 |
| QLPro [8] | 有<br>CodeQL | 部分<br>API 分析 | 部分<br>投票、路径 | 未列 | 未列 | 有<br>QL 查询 |
| Antiproof [9] | 有<br>合成检测器 | 部分<br>检测器驱动 | 有<br>可利用证明 | 未列 | 未列 | 有<br>静态检测器 |
| OpenAnt [10] | 部分<br>静态拆解 | 有<br>LLM 发现 | 有<br>对抗验证 | 未列 | 未列 | 未列 |
| QLCoder [4] | 有<br>查询执行 | 未列<br>已知 CVE | 部分<br>双版本命中 | 未列 | 未列 | 有<br>QL 查询 |

本项目一行描述现有设计和已实现入口，功能存在不代表全量基准已通过。修复验证中的项目测试及复扫，仍需由 PatchEval 的安全 PoC 和功能测试检验真实修复效果。Java 规则任务和 Go 修复任务均属于本方案必须覆盖的完整测试目标。

Semgrep CE 的规则替换与平台 Autofix 的 AI 补丁是两种能力；平台组合包含 Pro 引擎、Assistant、Agentic Workflows 和 Autofix，具体功能取决于产品开通范围。Copilot Autofix 本行限定为 CodeQL 告警修复，不包含 Copilot 其他产品能力。Antiproof、OpenAnt 的动态漏洞验证用于确认漏洞，不能据此推定它们提供补丁回归验证。

RepoAudit 当前官方实现包含 MetaScanAgent 和 DFBScanAgent，覆盖 C/C++、Java、Python、Go；其公开重点包括空指针、内存泄漏和释放后使用。[7] QLPro 采用生成、执行和修订三个角色协作，其 repairer 修订的是 QL 查询；论文 v3 明示实验数据仍有错误，需要改进。[8] 因此将 QLPro 列为研究参考，暂不作为正式成绩对照。

### 3 三个功能模块的竞品测试对照

**表9 按三个功能模块划分的竞品测试对照**

| 模块 | 优先对照对象 | 测试范围 | 比较目标 |
| --- | --- | --- | --- |
| 双引擎代码审计 | CodeQL CLI；Semgrep CE；Alibaba OpenCodeReview | RealVuln 26 项目、796 项标签；OWASP 1230 例 | 检出和误报、引擎增益、复核效果、耗时成本 |
| 代码修复 | Copilot Autofix；Semgrep Autofix<br>内部基线：同模型直接修复 | PatchEval 1000 任务、230 动态任务 | 安全与功能联合成功、可应用补丁、触发覆盖率、耗时成本 |
| 规则生成 | QLCoder<br>内部基线：同模型基础生成 | QLCoder 176 项 Java CVE、42 类 CWE | 查询可执行、漏洞命中、修复版区分、生成成本 |

代码审计重点比较发现与复核的收益；代码修复重点比较漏洞消除和功能保持；规则生成重点比较查询有效性。商业修复产品依赖前置告警，其触发覆盖率与触发后的修复成功率共同决定端到端表现。仅支持部分任务的竞品，成绩限于该共同范围；本项目的完整测试目标保持第一章所列数量。

QLCoder 是规则模块的正式外部对照。Antiproof 的检测器合成可用于扩展研究，但规则形式未核实为可运行 CodeQL 前，不进入 176 项 CodeQL 成功率主表。上述表格确定需要比较的能力与对象，实际优劣由后续测试结果给出。

### 参考资料

论文原报数值按所列版本与表号引用；产品能力依据官方公开说明。

[1] Pellew 与 Raza RealVuln 2026 论文 v1

全量范围与评分依据；第10页 Table 4。

[https://arxiv.org/abs/2604.13764v1](https://arxiv.org/abs/2604.13764v1)

[2] OWASP BenchmarkPython 官方项目

0.1 版本；expectedresults-0.1.csv 共 1230 例。

[https://github.com/OWASP-Benchmark/BenchmarkPython](https://github.com/OWASP-Benchmark/BenchmarkPython)

[3] PatchEval 2025 论文 v1

1000 项任务、230 项动态任务；第9页 Table 3。

[https://arxiv.org/abs/2511.11019v1](https://arxiv.org/abs/2511.11019v1)

[4] Wang 等 QLCoder ICLR 2026 正式论文

第8页 Table 1、第9页 Table 4。官方实现 https://github.com/neuralprogram/qlcoder。

[https://proceedings.iclr.cc/paper_files/paper/2026/hash/2adf01ab15adde8820622f7f24bd516b-Abstract-Conference.html](https://proceedings.iclr.cc/paper_files/paper/2026/hash/2adf01ab15adde8820622f7f24bd516b-Abstract-Conference.html)

[5] 用户提供的竞品材料

缺乏修复功能/只有建议没有修复.doc；代码审计低/代码审计效率低.doc；代码审计低/证据1.pdf。用于定位研究对象，功能判断依据原始论文与官方实现。

[6] Li 等 LLM based Vulnerability Detection at Project Scale An Empirical Study v2

对应所附证据1.pdf；未将跨实验环境耗时纳入功能范围比较。

[https://arxiv.org/abs/2601.19239v2](https://arxiv.org/abs/2601.19239v2)

[7] RepoAudit 官方实现

MetaScanAgent、DFBScanAgent 及语言范围。原论文 https://arxiv.org/abs/2501.18160v1。

[https://github.com/PurCL/RepoAudit](https://github.com/PurCL/RepoAudit)

[8] Hu 等 QLPro 论文 v3

第 III 节描述 API 分类和 QL 生成；页面 Comments 说明实验数据存在错误。

[https://arxiv.org/abs/2506.23644v3](https://arxiv.org/abs/2506.23644v3)

[9] Shakevsky 等 Antiproof 论文 v1

[https://arxiv.org/abs/2607.12316v1](https://arxiv.org/abs/2607.12316v1)

[10] Korda 与 Evron OpenAnt 论文 v2

[https://arxiv.org/abs/2606.19149v2](https://arxiv.org/abs/2606.19149v2)

[11] Semgrep CE 官方实现

[https://github.com/semgrep/semgrep](https://github.com/semgrep/semgrep)

[12] Alibaba OpenCodeReview 官方实现

全文件 scan、审查 Agent、规则匹配及定位反思模块。

[https://github.com/alibaba/open-code-review](https://github.com/alibaba/open-code-review)

[13] GitHub security and quality AI features 官方应用说明

CodeQL 告警、Copilot Autofix 补丁及质量评估范围。

[https://docs.github.com/en/enterprise-cloud@latest/code-security/responsible-use/security-and-quality-ai-features](https://docs.github.com/en/enterprise-cloud@latest/code-security/responsible-use/security-and-quality-ai-features)

[14] Semgrep Autofix 官方产品说明

2026年3月16日；Assistant、升级影响分析与第一方代码补丁。

[https://semgrep.dev/blog/2026/semgrep-autofix-public-beta/](https://semgrep.dev/blog/2026/semgrep-autofix-public-beta/)

[15] CodeQL 官方概述

查询执行、静态分析与自定义查询范围。

[https://codeql.github.com/docs/codeql-overview/about-codeql/](https://codeql.github.com/docs/codeql-overview/about-codeql/)

[16] Semgrep Rule defined fix 官方文档

基于 fix 或 fix-regex 的规则替换功能。

[https://docs.semgrep.dev/writing-rules/rule-defined-fix](https://docs.semgrep.dev/writing-rules/rule-defined-fix)

[17] Semgrep Agentic Workflows 官方产品说明

2026年7月28日；主动漏洞发现、Pro 引擎与 AI 推理组合。

[https://semgrep.dev/blog/2026/introducing-semgrep-agentic-workflows-automate-deep-vulnerability-hunting-at-scale/](https://semgrep.dev/blog/2026/introducing-semgrep-agentic-workflows-automate-deep-vulnerability-hunting-at-scale/)
