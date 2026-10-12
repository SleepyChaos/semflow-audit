# CodeQL 规则生成可靠性：论文阅读记录

调研日期：2026-10-03。优先2026年，补充2025年；本文记录实际读取范围，区分论文证据与本项目推断。关联[改进方案](../../design/development/rule-generation-redesign-plan.md)、[现有结果](../../benchmarks/reports/phase-one-test-results.md)。

## 1. 重点论文及阅读范围

| 文献 | 年份/状态 | 本次读取范围 | 与项目的关系 |
|---|---|---|---|
| QLCoder: A Query Synthesizer for Static Analysis of Security Vulnerabilities | ICLR 2026；首次预印本2025；主要核对arXiv v3，2026-03-19 | §3、§4，尤其Table 4/5，§5及LSP附录；OpenReview正文受验证拦截，使用作者arXiv全文 | 最直接的查询生成参考 |
| IRIS: LLM-Assisted Static Analysis for Detecting Security Vulnerabilities | ICLR 2025；首次预印本2024 | 2025 v3 §3、§5、Appendix A/C；取得PDF | 让AI推断规格，再通过模板转为查询 |
| CQLLM: A Framework for Generating CodeQL Security Vulnerability Detection Code Based on Large Language Model | Applied Sciences 2026, 16(1),517；2026-01-04 | 期刊公开索引；作者2025预印本全文§3–6，尤其Table 4；期刊PDF未取得 | 国内团队RAG/LoRA路线；避免混用版本数字 |
| QRS: A Rule-Synthesizing Neuro-Symbolic Triad for Autonomous Vulnerability Discovery | 2026-02-10 arXiv预印本 | §2.3–2.5、§3–5及部分附录；取得PDF | Python、分离查询修复上下文 |
| Towards Scalable and Cost-Efficient Vulnerability Detection: A Study on Automatic Query Generation | 2026-09-09 arXiv预印本 | §3–6，Tables 2/3；取得PDF | 新近生成/语法修复的实证研究 |
| CodeRAG-Bench: Can Retrieval Augment Code Generation? | Findings of NAACL 2025 | §2–4、检索/生成评价、chunking与局限；取得PDF | 分开测量检索成功和生成成功 |
| QLM: CodeQL Query Synthesis with Compositional PoC Validation | ICSE 2026 JAWs展示 | 官方会议摘要；本次未定位可核对的完整论文/代码 | 原子谓词与PoC验证的辅助启发，不作为已精读全文证据 |

阅读是在核对相关方法、实验与局限；没有声称逐页复现这些系统。作者和可引用条目另见 `rule-generation-references.bib`。PDF及下载失败记录保存在本地 `artifacts/research/rule-generation-2026-10-03/`，不提交完整论文。

## 2. 阅读所得与适用边界

### P1 QLCoder：语言工具和检索共同约束生成

作者将语义资料检索、CodeQL LSP、漏洞/修复版本执行验证接入循环。20个CVE消融中，完整方案成功率55%，移除LSP为25%，移除Doc/Ref为20%，Claude Code基线10%。全部176个Java CVE的合成成功率53.4%，并非总体漏洞准确率。模型之间表现差异明显；验证使用已知补丁，指标基于路径与补丁位置，不等价于独立未知项目金标。启发：提供符号定义与上一版查询，并保留外部泛化测试。[作者全文v3](https://arxiv.org/html/2511.08462v3)、[作者MIT许可LSP适配器](https://github.com/neuralprogram/codeql-lsp-mcp)。

### P2 IRIS：减少AI必须生成的QL部分

IRIS先提取候选API及类型/文档，LLM推断source/sink规格，再用模板转成CodeQL，并做上下文复审。它没有在该研究中推断sanitizer规格；不能把其结果泛化为自动生成所有安全逻辑。Java实验支持“让模型判断语义、由静态分析执行传播”的路线，但本项目Python/JS仍需重新验证。[2025全文](https://arxiv.org/html/2405.17238v3)、[ICLR正式条目](https://proceedings.iclr.cc/paper_files/paper/2025/hash/582d4e27fa24168f3af1f4582655034b-Abstract-Conference.html)。

### P3 CQLLM：RAG有用，微调不应默认优先

国内作者预印本列出广州大学、南方科技大学、鹏城实验室；采用文档/例子检索、重排及LoRA。2025预印本Table 4中，RAG无微调为72.48%执行成功，完整方案为56.38%，且分母298/321不同。结论还承认缺少逐样本位置评价。因此不能从该表直接认定“加微调更稳定”，也不能把CWE覆盖/告警数量当检测Precision。先改检索与运行验证更适合本项目。[2026期刊条目](https://www.mdpi.com/2076-3417/16/1/517)、[所读2025作者全文](https://www.preprints.org/manuscript/202510.1458/v1/download)、[作者代码](https://github.com/Arashiailing/CQLLM)。

### P4 QRS：修复上下文应携带失败查询

QRS在Python包上研究查询生成、语义审查及最终证据裁决。其修复子流程接收失败原始查询与stderr，用独立短上下文、默认三次预算。它的模型裁决与人工检查不能代替独立测试oracle；模型置信度也不能直接用于我方自动确认。可借鉴其修复输入及职责分离，无须立即引入多个自治代理。[全文§2.3](https://arxiv.org/html/2602.09774v1)。

### P5 2026年9月研究：语法专门修复与模型能力需分别测

研究把补丁模式理解、API资料获取、谓词生成、查询组装与语法修复分开，最多三次修复；多模型最初生成可编译查询数量很低，加入修复后部分模型改善。它也讨论高误报及可达性问题。启发是单独评估修复器，不能据模型通用排名选择CodeQL模型。Java、补丁种子及文件级匹配限制了向本项目直接转移数字。[全文§3–6](https://arxiv.org/html/2609.10412v1)。

### P6 CodeRAG-Bench：先确定资料是否取对

基准把检索和端到端可执行生成分别评价；发现相关资料获取与模型利用资料都是瓶颈。不同资料源/检索器收益不同，外部代码有时不如本仓库上下文；部分公开解答还可能泄露目标答案。启发：建立API检索金标、控制上下文、隔离修复答案与最终测试。[正式全文](https://aclanthology.org/2025.findings-naacl.176.pdf)。

### P7 QLM：组合式验证的补充线索

官方摘要提出把查询拆成可独立验证的原子谓词，并用来自补丁的最小PoC进行早期调试。全文与完整协议未核对，本次仅用它支持分步验证的设计探索；不将摘要性能数字列为方案承诺。[会议摘要](https://conf.researchr.org/details/icse-2026/jaws-2026-papers/56/QLM-CodeQL-Query-Synthesis-with-Compositional-PoC-Validation)。

## 3. 与成熟工具的结合

GitHub官方[Python](https://codeql.github.com/docs/codeql-language-guides/customizing-library-models-for-python/)和[JavaScript](https://codeql.github.com/docs/codeql-language-guides/customizing-library-models-for-javascript/)文档提供YAML数据扩展。但文档标注beta，不能直接假定最新条目都支持我方旧固定包。

本次只读核对本地：`codeql/python-all@4.0.10`及`codeql/javascript-all@2.4.0`的 `ApiGraphModelsExtensions.qll`均定义sourceModel、sinkModel、summaryModel；`codeql execute language-server --help`实际存在。尚未进行LSP握手、YAML模型集成或性能测试。框架模型因此应从已确认的扩展点开始，sanitizer/barrier及其他格式单独验证。

## 4. 调研结论

建议采用“**证据规格 → 分层检索 → 受限模型/谓词合成 → 类型与执行反馈 → 独立验收**”。这是综合论文与项目失败记录形成的设计推断，尚未验证收益。单纯添加向量库、提高预算或LoRA，不足以作为本次主要方案。具体链路、改动范围和实验门槛见改进方案。
