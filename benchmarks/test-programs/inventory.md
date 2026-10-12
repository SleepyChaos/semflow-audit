# 当前测试材料、对照与文献统计

统计日期：2026-10-08。范围：三个方向材料目录、既有书目/方法登记、历史材料清单和最近竞品记录。

[论文时效与横向对照覆盖核查](freshness-and-coverage-review.md)：43项登记保持；另列3篇新文献及4个补充工具候选，未合并为已收集/已运行数量。

## 数量与口径

| 对象 | 数量 | 含义 |
| --- | ---: | --- |
| 测试材料/任务候选 | 32 | 按当前主要用途分：通用13、专项19；不是32个独立可运行数据集 |
| 漏洞发现方向 | 16 | 含原目录13项，以及BAC-Bench、AACR-Bench、PyVul |
| QL规则方向 | 6 | 含公开框架、范例、失败归档和自建隐藏任务候选 |
| 修复方向 | 10 | 含安全修复、业务回归及相邻生成任务材料 |
| 主要外部对照 | 10 | 其中3个已有同OWASP48实跑，7个未同任务实跑 |
| 额外方法候选 | 8 | 作为复现/消融研究，不表示全部官方代码可运行 |
| 去重文献登记 | 43 | 论文、报告及摘要登记；预印本/正式版合并，不是通读数 |
| 本地PDF文件 | 25 | 对应21项文献，重复副本/版本不重复计文献 |
| 仅有本地HTML全文 | 1 | SecRepoBench |
| 其余文献登记 | 21 | 有链接/书目/阅读记录，尚未核对本地全文 |

原`collection-summary.json`的29项材料、24项论文是2026-10-05三方向目录收集快照。当前统计另外并入较早和近期研究登记，数量增加不代表本次又下载了全部增量。

## 两类材料目录

主分类用于管理，可按具体任务复用；跨类别复用不重复计材料总数。规模单位不同不能相加称样本总量。

### A类：通用基准（13项）

| 材料 | 方向 | 当前落地与限制 |
| --- | --- | --- |
| [OWASP BenchmarkPython](https://github.com/OWASP-Benchmark/BenchmarkPython) | 发现/复审 | 完整源码与标签：1230例，452正/778负，14类。全量CodeQL已跑；AI全量未跑，已有冻结48例验收。 |
| [RealVuln](https://github.com/kolega-ai/Real-Vuln-Benchmark) | 发现/复审 | 140仓库元数据；Flask/DVNA两项目源码。31个主条件+5个误报陷阱；累计29/31是开发结果。 |
| [OpenSSF CVE Benchmark](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | 发现/复审 | 223 CVE元数据已存；旧20项pilot已暴露。任务金标与源码需另外准备。 |
| [6个新增JS项目配对快照](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | 发现/复审 | 6个JS项目、12个前后快照已存；4模块oracle校准完成，尚无获准正式隐藏修复集。 |
| [SecBench.js](https://github.com/cristianstaicu/SecBench.js) | 发现/复审 | 框架及600项索引已存；npm目标包缺失，不能直接称600项可运行。 |
| [SecJS / ForgeJS / JudgeJS](https://github.com/SecJS-Vuln-Benchmark/SecJS-Benchmark) | 发现/复审 | ForgeJS/JudgeJS框架与元数据；ArenaJS未公开。 |
| [eyeballvul](https://github.com/timothee-chauvin/eyeballvul) | 发现/复审 | 固定版本目录/元数据；未收齐目标源码。2024历史数据来源。 |
| [VICBench](https://arxiv.org/abs/2608.12246) | 发现/复审 | 论文已存；数据公开状态未核准。 |
| [当前语言QL独立评测候选](https://github.com/OWASP-Benchmark/BenchmarkPython) | 规则 | 来源候选与开发实验已有；正式独立任务、参考QL及隐藏正反例未核准。 |
| [PatchEval](https://github.com/bytedance/PatchEval) | 修复/回归 | 1000项JSON与框架已存（Py404/JS300/Go296）；176条非空测试命令；容器镜像/全源码缺失。 |
| [Vul4Py](https://github.com/tabudz/vul4py) | 修复/回归 | 100项索引/harness已存；目标快照未齐，联合oracle判定需校准。 |
| [BugsInPy](https://github.com/soarsmu/BugsInPy) | 修复/回归 | 框架及501份bug.info已存；非501项已复现安全漏洞，只作功能回归辅助。 |
| [PyVul](https://github.com/billquan/PyVul) | 发现/复审 | 论文/仓库入口已登记；未下载并冻结数据。 |

### B类：专项同任务（19项）

| 材料 | 方向 | 当前落地与限制 |
| --- | --- | --- |
| [Tencent VulnGym](https://github.com/Tencent/VulnGym) | 发现/复审 | 184报告、408入口标注（393人工确认）已存；目标仓库未齐。用于取证/定位。 |
| [SastBench](https://github.com/RivalSecurity/sastbench) | 发现/复审 | 2737告警原JSON已存；Py/JS/TS候选1313条。近似负标签须审核，不能测从零发现召回。 |
| [CrossCommitVuln-Bench](https://github.com/motornomad/crosscommitvuln-bench) | 发现/复审 | 复制包55完整条目；论文原15 CVE与追加40条分开；原项目源码不齐。 |
| [Vulnerability Localization Benchmark (VLoc Bench)](https://github.com/cisco-foundation-ai/vulnerability-localization-benchmark) | 发现/复审 | 官方报告/入口已核验；本地下载失败。 |
| [VEX-Bench](https://github.com/steven1518/vex-bench) | 发现/复审 | 论文及官方来源已核验；本地下载失败。任务是供应链可利用性。 |
| [QLCoder / CWE-Bench tasks](https://github.com/neuralprogram/QLCoder) | 规则 | 框架、任务索引、作者输出已存；Java/C主任务。216项目行/1493修复索引不是独立成功样本数。 |
| [CWE-Bench Java Spark snapshots](https://github.com/perwendel/spark) | 规则 | 漏洞与首修复源码快照已存；首修复未必完整；Java不匹配当前主语言。 |
| [CQLLM Python rule samples and task workbook](https://github.com/Arashiailing/CQLLM) | 规则 | Python QL压缩包、查询、提示CSV和工作簿已存；缺独立隐藏金标，需排除RAG重叠。 |
| [IRIS v2 / CWE-Bench-Java](https://github.com/iris-sast/iris) | 规则 | 固定版本树/许可证元数据与论文；Java任务，原目标项目集未齐。 |
| [Automatic Query Generation replication package](https://arxiv.org/abs/2609.10412) | 规则 | 论文已存；复制包下载为空/无效，不计有效数据。 |
| [Execution-calibrated patching reproduction](https://zenodo.org/records/21645415) | 修复/回归 | 完整复制包已存；8个旧小样已测仅作开发。作者数据库不是本平台成绩。 |
| [EduCollab / Detect-Repair-Verify](https://github.com/Hahappyppy2024/EmpricalVDR) | 修复/回归 | 所选197个文件188个通过Git blob核对，9缺失；非完整项目快照。 |
| [VulnRepairEval](https://arxiv.org/abs/2509.03331) | 修复/回归 | 论文已存；23个Python PoC数据发布未核准，服务依赖暂不符合主评测边界。 |
| [RealSec-bench](https://aclanthology.org/2026.findings-acl.1786/) | 修复/回归 | 论文已存，105个Java安全生成任务；不能直接当Py/JS漏洞修复任务。 |
| [SecRepoBench](https://arxiv.org/abs/2504.21205) | 修复/回归 | HTML论文已存；C/C++安全补全任务，数据/框架未收齐。 |
| [PredicateFix artifact](https://doi.org/10.6084/m9.figshare.26956228) | 修复/回归 | 官方论文/归档入口已核验；本地归档下载失败。 |
| [SEC-bench](https://github.com/SEC-bench/SEC-bench) | 修复/回归 | 官方NeurIPS2025论文与数据来源已核验；本地下载失败；C/C++环境待支持。 |
| [BAC-Bench / ABSENTIA task](https://github.com/avduarte333/Absentia) | 发现/复审 | 在线核验30条/25仓库/9框架，Py18/TS9/JS3；索引及上游源码未本地冻结，检测器未发布。 |
| [AACR-Bench](https://huggingface.co/datasets/Alibaba-Aone/aacr-bench) | 发现/复审 | 2145评论标签与714条Py/JS/TS子集已存；非全安全评论；完整PR源码上下文缺失。 |

## 主要外部对照（10个）

| 工具/项目 | 当前证据 | 本轮用途 |
| --- | --- | --- |
| [CodeQL](https://codeql.github.com/) | 同OWASP48实跑；全量静态也已有 | 通用固定静态对照；专项按原任务配置 |
| [Bandit](https://github.com/PyCQA/bandit) | 1.9.4同OWASP48实跑 | Python通用静态对照 |
| [Alibaba Open Code Review](https://github.com/alibaba/open-code-review) | a758d9cb同OWASP48实跑；AACR任务尚未跑 | 通用LLM工具；后续评论复审专项 |
| [Semgrep CE](https://github.com/semgrep/semgrep) | 来源已登记，尚未实跑 | 通用CE对照；区分商业/Pro |
| [Frame](https://github.com/lambdasec/frame) | 官方报告参照，未实跑 | 通用发现候选 |
| [VyQL](https://github.com/vyprai/vyql) | 官方报告参照，未实跑 | 通用发现候选，需检查基准暴露 |
| [Cyfendo](https://cyfendo.com/benchmarks) | 厂商自报，闭源服务未接入 | 参考结果，不能称受控比较 |
| [ABSENTIA](https://github.com/avduarte333/Absentia) | 论文与数据入口，检测器尚未公开 | BAC-Bench专项 |
| [IRIS](https://github.com/iris-sast/iris) | 论文与仓库元数据，未实跑 | Java静态模型扩充专项，当前语言不匹配 |
| [RepoAudit](https://github.com/PurCL/RepoAudit) | 论文与仓库入口，未实跑 | Agent取证专项，需对齐漏洞类型/语言 |

另8个方法候选：**QLCoder、CQLLM、QRS、ARQ、QLPro、PredicateFix、SemTaint、LLM4PFA**。有框架、选定样例和论文参考等不同状态；SemTaint同名JavaWeb仓库不能当原JS论文复制包。平台自己的NoRAG/检索模式/Scout/复审消融不计外部工具数。

## 文献登记（43项）

按登记引用/正式发表年份：2026年29项、2025年12项、2024年1项、2023年1项。41项引用年为2025–2026；引用年不等于首次公开年。QLCoder首稿2025，IRIS/Vul-RAG首稿2024。历史SecBench.js与eyeballvul只作为数据来源；QLM目前是研讨会摘要登记，不算已核准完整论文。

- 发现/复审优先：RealVuln、VulnGym、SastBench、ABSENTIA、AACR-Bench、RepoAudit、跨语言误报研究。
- 规则优先：QLCoder、IRIS、CQLLM、QRS、ARQ、QLPro、Automatic Query Generation；CodeRAG-Bench辅助设计检索评价。
- 修复优先：PatchEval、Vul4Py、Execution-calibrated patching、PredicateFix、VulnRepairEval、Detect-Repair-Verify与自动漏洞修复SoK。

[逐项标题、年份、链接及本地状态](../catalog/current-papers.md)。全文阅读范围查原研究记录；存有PDF不代表通读或结论已复现。

## 尚未就绪的关键项

1. BAC-Bench索引/上游源码固定、金标隔离和访问控制匹配器；ABSENTIA官方实跑还待检测器发布。
2. 新的通用发现验收样本及统一逐告警盲审；现有48例已暴露，不能重复算新盲测。
3. Py/JS独立规则任务：参考QL可解、隐藏正反例、跨项目迁移与RAG范例去重。
4. 修复正式任务：完整快照、安全/业务联合oracle校准；目前不能把已有4模块校准写成正式修复成功率。

本次只整理材料和计划，没有追加模型调用。原始测试标签、代码快照、PDF继续留原路径与保密边界，未导入生产RAG。统计可通过[清单脚本](../../system/scripts/benchmarks/current_test_inventory.py)重建；完整字段见[JSON](../manifests/current-test-inventory.json)。
