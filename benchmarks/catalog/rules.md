# rules 材料清单

核查日期：2026-10-05。已完成一轮检索；上游规模不等于本地可运行规模。

## 数据与复制包

| 材料 | 已收集状态 / 固定版本 | 测什么 | 限制与许可 |
| --- | --- | --- | --- |
| [QLCoder / CWE-Bench tasks](https://github.com/neuralprogram/QLCoder) | complete_framework_task_indexes_and_author_outputs；`b879ac2c90aac7fcc0b2e73caf117c2a12bf20e9` | CodeQL生成、执行反馈、定位评测流程参考 | project_info216行、fix_info1493行，不等于独立216漏洞或1493规则；原论文Java/C，当前Python/JS不能直接套；生成答案/patch/标签需隔离；MIT framework; upstream separate；历史：QLCoder paper used earlier for design; tasks newly archived |
| [CWE-Bench Java Spark snapshots](https://github.com/perwendel/spark) | vulnerable_and_first_fix_source_snapshots；`5316c0d0f057daaf556c3907c20df975f7bf8a8a vulnerable / 030e9d00125cbd1ad759668f85488aba1019c668 first-fix` | Java参考的真实库QL执行流程 | first-fix未确认完整修复，不直接当安全oracle；Java不属于当前平台主语言；upstream license retained; review required；历史：not evaluated |
| [CQLLM Python rule samples and task workbook](https://github.com/Arashiailing/CQLLM) | selected_python_zip_queries_prompt_csv_xlsx；`9e2abe086b7b2cc55fa22c0fc9305e972b16157f` | Python QL生成参考、原方法任务结构 | 不是完整release；zip/工作簿未转为独立隐藏集；官方QL示例可能与RAG重叠；无源码项目gold完整性证明；repository license unresolved; local reference only；历史：not evaluated; overlap audit pending |
| [IRIS v2 / CWE-Bench-Java](https://github.com/iris-sast/iris) | commit_tree_license_metadata_only；`v2 fixed sha in iris-v2-commit.json` | source/sink规格扩展与完整项目评测参考 | 未下载完整IRIS项目集；不能把作者结果作为平台结果；MIT framework; verify actual LICENSE and upstream licenses；历史：earlier paper consulted |
| [Automatic Query Generation replication package](https://arxiv.org/abs/2609.10412) | failed_empty_archive；`paper arxiv v1` | 编译率、检测率与耗时定义参考 | ZIP为0字节、页面为空，下载失败；不计可用数据；论文PDF已保存；unverified dataset license；历史：not evaluated |
| [当前语言QL独立评测候选](https://github.com/OWASP-Benchmark/BenchmarkPython) | source_candidates_only_tasks_not_prepared；`see project-pair manifest and OWASP fixed commit` | 标准规则漏检目标→新规则检测；隐藏同根因/安全变体 | 需先固定CodeQL基线并确认漏检，再构建三输入任务；与141官方RAG范例、旧18次任务隔离；本轮没有制作新的黄金QL答案；upstream and derived fixture licenses to record；历史：not evaluated |

## 论文与专业来源

正式论文、预印本及官方技术报告分别标注；同一工作不同版本不重复计算。

| 文献 | 年份 / 状态 | 价值与核实机构 |
| --- | --- | --- |
| [QLCoder: A Query Synthesizer for Static Analysis of Security Vulnerabilities](https://openreview.net/forum?id=J91IKwJrqv) | 2026；ICLR 2026 | RAG/LSP/执行反馈闭环；arxiv v5同一工作不重复计数；UPenn / Johns Hopkins / Cornell verified from paper |
| [IRIS: LLM-Assisted Static Analysis for Detecting Security Vulnerabilities](https://arxiv.org/abs/2405.17238) | 2025；ICLR 2025; arxiv first posted 2024 | 污点规格而非自由QL全文生成；UPenn / Cornell verified from paper |
| [CQLLM: A Framework for Generating CodeQL Security Vulnerability Detection Code Based on Large Language Model](https://doi.org/10.3390/app16010517) | 2026；Applied Sciences 16(1):517, published 2026-01-04 | 国内Python QL生成、知识/范例、检查执行；广州大学 / 南方科技大学 / 鹏城实验室，论文首页核实 |
| [QRS: A Rule-Synthesizing Neuro-Symbolic Triad for Autonomous Vulnerability Discovery](https://arxiv.org/abs/2602.09774) | 2026；arXiv preprint | 受约束规格和query-review-sanitize；University of Piraeus / Athena Research Centre verified from paper |
| [Towards Scalable and Cost-Efficient Vulnerability Detection: A Study on Automatic Query Generation](https://arxiv.org/abs/2609.10412) | 2026；arXiv preprint | 近期QL生成能力、成本与覆盖指标；Singapore Management University / Monash / University of Sydney verified from paper |
| [CodeRAG-Bench: Can Retrieval Augment Code Generation?](https://aclanthology.org/2025.findings-naacl.176/) | 2025；Findings of NAACL 2025 | 分开评估检索相关性和下游生成；非QL黄金集；not verified |

本地路径及下载状态见同名 JSON；逐文件校验见 `../manifests/local-integrity.json`。所有 raw/论文仅本地保存，未加入 RAG。
