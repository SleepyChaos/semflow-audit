# 论文资料与三项研究贡献建议

核查日期：2026-10-03（北京时间）。本页只使用论文原文、出版方和作者仓库。预印本、正式出版和代码可获得性分别标明；论文报告的数字不能作为本平台成绩。论文优先 2026，保留与研究问题直接相关的 2025 工作。旧预印本的新版或正式出版不能宣传成首次提出的新方法。

## 1. 从最早讨论延续的研究问题

用户最早希望研究 AI 增强传统静态审计，而不是另写一个纯 LLM 扫描器；之后指出旧平台两个问题：知识库不是真实 RAG，以及“增量漏洞”锚点不可靠。当前四阶段设计把规则、静态扫描、证据复审、修复验证串起来，论文应围绕这两个原始问题及其下游验证成本展开。

建议主问题：**在相同模型与预算下，版本约束的规则知识、按需代码取证和独立修复验证，能否提高 Python/JavaScript 项目的真实漏洞发现与正确修复率，同时降低人工复核和重复扫描成本？**

“综合平台”是工程成果。研究贡献需要有明确方法、反例、可独立消融的机制与数据。

## 2. 优先阅读的一手论文

### 2026 工作

| 论文、日期与状态 | 机构／来源 | 与平台的关系、公开材料与适配边界 |
|---|---|---|
| **An Empirical Analysis of CodeQL False Positives and Query Refinements for Java Vulnerabilities**；2026-09-03 首投，09-15 v2；预印本 | Drexel、Cornell；[摘要及版本](https://arxiv.org/abs/2609.04535)、[全文](https://arxiv.org/html/2609.04535v2) | 分析 Java 误报类型和规则修订；人工抽样 500 条路径/位置。应借用误报分类与真阳性保留率，而不是直接移植 Java 得分。本次未核实独立完整复现包。 |
| **Towards Scalable and Cost-Efficient Vulnerability Detection: A Study on Automatic Query Generation**；2026-09-09；预印本 | SMU、Monash、Sydney；[论文](https://arxiv.org/abs/2609.10412) | CVE 模式→QL；Java 数据，强调成本与文件级指标。可引用规则摊销成本的研究动机；与本项目 Python/JS 实测需要分开。全文给出数据构造过程，本次未核实独立作者代码仓库。 |
| **Fixing, Breaking, or Faking It? An Execution-Calibrated Evaluation of LLM Vulnerability Patching in JavaScript, Python, Go, and Java, and the Limits of LLM-as-Judge**；2026-09-02；Journal of Cybersecurity and Privacy 6(5), 153 | FH JOANNEUM、Graz；[出版方全文](https://www.mdpi.com/2624-800X/6/5/153)、[复现包](https://zenodo.org/records/21645415) | 直接适配 JS/Python 修复评价。应使用执行与功能保持判据；两位 LLM judge 互相同意不足以证明补丁正确。复现包 CC BY 4.0，正式跑前固定版本并检查 oracle 完整性。 |
| **Vul4Py: Benchmarking Automated Vulnerability Repair in Python with Paired Exploit and Functional Oracles**；2026-08-01；预印本 | SMU、Monash、UNSW；[论文](https://arxiv.org/abs/2608.00692)、[作者仓库](https://github.com/tabudz/vul4py) | 最贴当前 Python 修复链：100 漏洞、60 项目、60 CWE；每例有 exploit 与功能 oracle、固定环境。需要每例安装依赖的专用环境，不能宣称当前仅 syntax/通用 pytest 验证器已自动支持全部实例。 |
| **ARQ: Agentic CodeQL Query Refinement for C/C++ Vulnerability Detection**；2026-08-21；预印本 | Columbia；[论文](https://arxiv.org/abs/2608.20637)、[全文](https://arxiv.org/html/2608.20637v1) | 通过生成程序、执行 oracle 与查询判定不一致来修订 QL；主要是 C/C++ 内存安全。证明“编译通过”不足以说明规则正确。Juliet/FormAI 是相关方法资料，当前 Python/JS 平台不能以这些分数证明能力。本次未核实作者完整独立公开包。 |
| **Securing AI-Generated Code: A Just-in-Time Vulnerability Detection and Remediation Pipeline**；2026-08-17；预印本、Georgia Tech 硕士 practicum | Mikhail Surikov；[论文](https://arxiv.org/abs/2608.16187) | Python CodeQL+Bandit+LLM 扫描、修复、复扫，与综合链路非常接近。可作较轻工程基线。其“扫描告警下降”不等于独立 oracle 下的正确修复，需避免沿用这一单一终点。 |
| **RealSec-bench: A Benchmark for Evaluating Secure Code Generation in Real-World Repositories**；2026-07；Findings ACL 2026 正式论文 | 作者 Yanlin Wang 等；[官方条目](https://aclanthology.org/2026.findings-acl.1786/)、[数据代码](https://github.com/DeepSoftwareAnalytics/Realsec-code-Bench) | 105 个 Java 实例、19 CWE；SecurePass@K 同时考虑功能与安全。报告通用 RAG 的安全收益有限，因此本项目必须把检索质量和安全检测质量分开测。Java 数据用于方法引用／未来扩展，不直接纳入当前主榜。机构在本次 HTML 元数据中未核实，不按姓名推断国别。 |
| **Revisiting Vul-RAG: Reproducibility and Replicability of RAG-based Vulnerability Detection with Open-Weight Models**；2026-06-03；作者注明已接收 AI&CCPS/ARES 2026 workshop | Sabrina Kaniewski、Fabian Schmidt、Tobias Heer；[原文与材料链接](https://arxiv.org/abs/2606.04739) | 本地开权重复现，暴露 vulnerable/fixed 双对判别的性能瓶颈。适合引用可复现性和 pairwise accuracy；应固定模型与知识版本。workshop 与顶会主会区别标明。 |
| **Persistent Human Feedback, LLMs, and Static Analyzers for Secure Code Generation and Vulnerability Detection**；2026-02-05；预印本 | TU Clausthal；[论文](https://arxiv.org/abs/2602.05868) | 人工真值与 CodeQL/Semgrep 逐例不一致；提出持久化反馈 RAG 的概念框架。说明不能把 CodeQL 当唯一安全真值，也说明“反馈闭环”已有相关设计，需进一步具体化。本次未核实完整开放数据。 |
| **Reducing False Positives in Static Bug Detection with LLMs: An Empirical Study in Industry**；2026-01-26；预印本 | 国内腾讯工业场景，作者 Xueying Du 等；[论文](https://arxiv.org/abs/2601.18844) | 433 告警、三类 bug，适合引用工业复审成本与召回保护；属于静态 bug 误报复审，不可把其效果直接推广到全部安全 CWE。企业数据公开程度需按原文另查，不能默认可下载。 |

### 2025 核心相关工作及较新正式版本

| 论文与状态 | 来源 | 建议用途与新意风险 |
|---|---|---|
| **QLCoder: A Query Synthesizer for Static Analysis of Security Vulnerabilities**；2025-11-11 首投，2026-08-26 v5 | UPenn、Johns Hopkins、Cornell；[论文及版本](https://arxiv.org/abs/2511.08462)、[代码](https://github.com/neuralprogram/qlcoder) | 已使用 RAG、LSP/MCP 和执行反馈合成 QL，在 Java vulnerable/fixed 版本评价。是规则生成最重要近邻。“使用 RAG 生成 CodeQL”单独不够新。优先复现相同预算下无检索／文档检索／版本与项目知识检索。 |
| **IRIS: LLM-Assisted Static Analysis for Detecting Security Vulnerabilities**；ICLR 2025 正式论文；预印本始于 2024 | UPenn、Cornell；[ICLR 正式论文](https://openreview.net/pdf?id=9LdJDU7E91)、[代码与数据](https://github.com/iris-sast/iris) | 源/汇规范补全 + CodeQL + 上下文误报过滤，直接对应 AI 介入边界。正式实验为 Java，仓库后续增加数据；引用应固定论文版本与数据版本，不能把当前 213 CVE 与论文原始 120 混为一谈。 |
| **QLPro: Automated Code Vulnerability Discovery via LLM and Static Code Analysis Integration**；2025-06-30；预印本 | 中科院信工所、国科大；[论文](https://arxiv.org/abs/2506.23644) | 国内近邻，污点规格分类配对、投票与规则生成；JavaTest 10 项目/62 漏洞。本次未在原文核实公开独立仓库，先作论文对比而非声称已经复现的竞品。 |
| **Minimizing False Positives in Static Bug Detection via LLM-Enhanced Path Feasibility Analysis**；2025-06-12；预印本 | Xueying Du 等；[论文](https://arxiv.org/abs/2506.10322) | LLM4PFA 按需上下文与路径可行性推理，是语义复审近邻。需比较静态告警复审的 TP 保留、FP 降低和取证预算，而不是只比较答案文本。 |
| **SoK: Automated Vulnerability Repair: Methods, Tools, and Assessments**；USENIX Security 2025 正式论文 | 华中科技大学、UCCS；[官方论文与 BibTeX](https://www.usenix.org/conference/usenixsecurity25/presentation/hu-yiwei)、[材料](https://github.com/SoK-Vul4C/SoK) | 国内主导修复综述与 Vul4C。作为分析—生成—验证分类和修复实验设计引用；Vul4C/Vul4J 不适配当前语言。官网正文与导出作者 Zhen Li/Liu 存在不一致，最终投稿以 PDF 为准。 |
| **Vul-RAG: Enhancing LLM-based Vulnerability Detection via Knowledge-level RAG**；TOSEM 正式条目显示 2026-09-16；预印本首投 2024，v3 为 2025-06-17 | 复旦、阿里等；[出版方 DOI](https://doi.org/10.1145/3797277)、[公开预印本](https://arxiv.org/abs/2406.11147) | 国内重要知识级 RAG 近邻；通过历史漏洞/修复提取根因知识，主要 Linux/C 语境。正式 DOI 页面抓取受 403 限制，标题、机构、日期依据出版方索引，方法依据公开原文；本次不声称完整阅读正式版。严格“首次公开不早于 2025”时该项只作背景，不能伪装为全新 2026 方法。 |

## 3. 建议锚定的三项贡献

### 贡献一：与依赖版本和项目上下文绑定的、经独立用例验收的规则合成

保留用户的 RAG 规则方向，但名称建议收紧。输入为 CWE/需求、真实确认缺陷、项目 API 和锁定的 CodeQL pack；检索输出保存文档版本、digest、引用，生成策略明确区分模型补全、扩展原规则和新查询。编译、公开训练例、人工批准例、独立留出例分别验收，合格规则才进入后续扫描。

当前已具备引用记录、固定依赖、编译反馈、正反例批准与发布门槛；**独立留出规则测试集、项目 API 模型抽取和自动知识质量分层仍需实验建设**。模型自己生成的一正一反仅证明样例一致，无法证明泛化。

可证伪假设：在相同模型、调用数和反馈预算下，版本与项目知识检索能提高独立留出样本的正确检测率，且降低编译失败和良性近似例误报。必须纳入 QLCoder 式文档 RAG 近邻，而非仅对比无知识提示。

### 贡献二：证据约束、预算可控且允许弃权的语义复审与补充发现

把“精准语义化”改为方法描述，精准程度由实验决定。AI 按需读取源码、搜索调用点、查询批准规则；每次证据包含真实快照、位置和 digest。输出需标注来源、原告警关联或新增位置、根因、尚未验证的假设；无证据或证据不足则弃权。人类确认与模型建议分开计数。

当前引用真实性、预算、弃权与人工确认已有实现；**调用者查询仍是 Python 语法级/JS 文本级线索，不是完整可行调用图；位置不同也不自动证明不同根因**。论文新增漏洞计数必须由人工根因去重，必要时重放 exploit，不能把 `new_location` 直接当独立增量漏洞。

可证伪假设：主动取证优于同预算一次性上下文复审，并在相同 TP 保留率下降低 FP 和人工复核时间。对“已知静态告警复审”和“静态未发现漏洞补充”分别报分；确认成本也进入总成本。

### 贡献三：共享证据、独立双 oracle 的审计—修复—规则反馈闭环

这是第三项建议。已确认缺陷作为修复与候选规则的共同输入，修复发生在隔离副本，diff 与快照关联，使用漏洞 oracle、原功能测试和完整冻结规则复扫分别验收；通过验证的根因知识与规则版本随后用于留出的变体项目，衡量可迁移收益。

**普通“发现→修复→复扫”已有先行工作，不宜直接声称原创。**研究价值在于共享且可追溯的证据如何降低上下文成本、如何阻止无根因替换/过度修复、如何以跨项目独立 oracle 验证反馈规则。本平台当前有隔离副本、diff、测试与复扫记录；**通用 exploit oracle 注册、自动反馈入库、跨项目变体迁移实验尚未全部实现**。报告中必须区分工程已具备部分和论文待验证机制。

可证伪假设：与独立的扫描代理+修复代理相比，共享确认根因和证据可提升安全且保持功能的正确修复率；经过独立验证的反馈规则在未知项目提升召回且不破坏良性对照。

## 4. 论文实验最低要求

1. 先固定 Python/JS、4–6 个可实现 CWE，再扩大语言。Java/C 标准集作为相关工作，不计当前支持率。
2. 主数据使用真实 vulnerable/fixed 项目与双 oracle；自建配对微样本用于解释机制、覆盖边界和检索消融。两类分开报告。
3. 修复必须满足安全测试和功能保持。复扫零告警、编译通过、LLM judge 同意均不等于正确补丁。
4. 知识库禁止纳入测试项目的补丁、同一 CVE 的描述与近重复片段。按项目/CVE 家族划分，固定生成时间、模型版本、检索语料和依赖包。
5. 人工裁决至少两人盲评，记录分歧；AI 待确认记录不计新增 TP。对不存在可靠 oracle 的业务逻辑漏洞单列案例研究。
6. 检测报告 precision/recall/F1、配对双正确率、每 CWE 宏平均、弃权覆盖率；复审报告 TP 保留和 FP 降低；修复报告安全+功能联合通过与人工语义确认。
7. 速度分别记录冷提取、热查询、AI取证、修复验证、规则生成和复用摊销；失败和超时保持分母。至少三次重复，记录中位数、范围、机器与 token/call 预算。
8. 核心消融：无 RAG/BM25/混合检索；一次性上下文/主动取证；仅复扫/双 oracle；无反馈/人工确认后反馈。先完成这些，竞品数量不是越多越好。

## 5. 验收时可用的结论措辞

- 可以说：“实现了四阶段可追溯的混合审计原型，普通测试及真实 CodeQL/Docker 链路验证见项目测试报告。”
- 有实际模型实验后再说：“在指定数据、CWE、模型和预算上改善了某项指标”，给出区间及失败数。
- 当前不应说：“已证明全面准确”“RAG 天然提高安全性”“三个功能就是三个学术创新”“所有静态未发现的位置都是增量漏洞”。

最终论文推荐聚焦 **证据约束的混合审计方法及可验证反馈**，以规则知识与修复闭环为两个可消融支撑机制。这样比把三个平行功能强行包装成三项原创更稳健。
