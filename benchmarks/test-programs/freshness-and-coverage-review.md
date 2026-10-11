# 论文时效与横向对照覆盖核查

核查日期：2026-10-08。结论：**论文时效基本充足；已登记的发现对照类型较广，但实际横向比较和规则/修复对照仍不充分。** 优先补同任务可运行组及评价门槛。

## 1. 论文够不够新

现有43项去重登记，引用年2026计29项、2025计12项、历史2024/2023各1项。按引用年41/43为2025–2026，约95.3%；这不是“首次研究出现于2025–2026”的比例。

本次在线核对31条arXiv记录的标题、首发/修订日期，以及11条正式发表记录（两者有交集）。核查是元数据/相关摘要与方法说明，不表示重新通读43篇。SEC-bench延续此前官方核验，VLoc报告、QLM摘要和历史SecBench.js没有新增完整发表核验。逐项状态见[文献表](../catalog/current-papers.md)与[机器核查记录](../manifests/freshness-and-coverage-review.json)。

### 三个方向的近期代表

| 方向 | 文献 | 已核准日期/状态 | 适配性 |
| --- | --- | --- | --- |
| 发现 | [ABSENTIA](https://arxiv.org/abs/2610.00977) | 首发2026-10-01，预印本 | Web访问控制，Py/JS/TS，与业务语义相关 |
| 发现 | [VulnGym](https://arxiv.org/abs/2608.02001) | 首发2026-08-03 | 仓库级Agent取证，而非函数片段分类 |
| 规则 | [Automatic Query Generation](https://arxiv.org/abs/2609.10412) | 首发2026-09-09 | 生成CodeQL及成本比较；复制包仍缺有效下载 |
| 规则 | [ARQ](https://arxiv.org/abs/2608.20637) | 首发2026-08-21 | 查询精炼、执行反馈；C/C++任务不能直接与Py/JS求提升 |
| 规则 | [QLCoder](https://arxiv.org/abs/2511.08462) | 首发2025-11-11；最新arXiv版2026-08-26；ICLR2026正式发表 | 强方法对照；具体成绩须固定同一论文版本，Java主任务不匹配当前语言 |
| 修复 | [Vul4Py](https://arxiv.org/abs/2608.00692) | 首发2026-08-01，预印本 | Python安全+功能联合oracle；当前还需要本地准入校准 |
| 修复 | [Execution-calibrated patching](https://www.mdpi.com/2624-800X/6/5/153/notes) | 正式记录2026-09-02 | Py/JS相关，联合验证与LLM裁决局限 |
| 修复 | [PredicateFix](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/117/PredicateFix-Repairing-Static-Analysis-Alerts-with-Bridging-Predicates) | ICSE2026 Research Track；有2025预印本 | 规则谓词引导RAG修复；静态告警修复不等于全部安全/业务联合成功 |

### 不能只按年份判断的部分

- [Vul-RAG](https://doi.org/10.1145/3797277)正式发表于TOSEM，记录日期2026-09-16；但[首次公开](https://arxiv.org/abs/2406.11147)是2024-06-17。可以引用正式2026版，不能说方法首次提出于2026。
- [IRIS](https://arxiv.org/abs/2405.17238)首稿2024，正式ICLR2025；它是重要混合分析参照，不必为了追新删除。
- SecRepoBench虽然登记2025引用年，[arXiv最新版本](https://arxiv.org/abs/2504.21205)已是2026-02-14；书目新旧与实验实际使用版本分开登记。
- QLM当前登记为研讨会摘要；arXiv DOI或OpenReview链接本身不证明同行评审/正式录用。最新预印本、正式主会、研讨会、技术报告和厂商自报要分层引用。
- RepoAudit原登记标题已纠正为[正式ICML2025标题](https://proceedings.mlr.press/v267/guo25n.html)：*RepoAudit: An Autonomous LLM-Agent for Repository-Level Code Auditing*。

### 本次发现的3项补充候选

以下单列候选，尚未计入当前43项，也未下载/复现完整工件。

| 文献 | 首发/当前记录 | 与平台相关的缺口 | 比较限制 |
| --- | --- | --- | --- |
| [Knowledge-Enhanced Agentic Vulnerability Repair / KeaRepair](https://arxiv.org/abs/2607.00820) | 2026-07-01预印本 | 真实程序事实诊断、双视角知识、ReAct取证及补丁反馈，与计划中的语义修复十分接近 | 主实验55个C/C++漏洞；不能把作者修复率直接比较本平台Py/JS |
| [AgenticRepair](https://arxiv.org/abs/2607.29422) | 2026-07-31；arXiv注明IEEE TSE审稿中 | 结构、运行和历史三类上下文编排，检验“增加语义上下文”是否独立有效 | SEC-bench sanitizer任务与当前纯单元边界不同；审稿中不是已发表TSE |
| [How Safe Are AI-Generated Patches?](https://arxiv.org/abs/2507.02976) | 2025-06-30首发，2025-12-29修订 | 检查修复是否引入新安全问题；补足只看原漏洞消失的评价 | 普通程序修复的安全风险研究，不能当专门AVR成功率基准 |

推荐优先读这3项及现有Vul4Py/PredicateFix。已有最新发现和规则论文足够支持下一阶段，修复的上下文工程与新漏洞评价更需要深入。

## 2. 横向比较够不够全面

10个主要外部对照与8个方法候选不等于18个已完成的横向实验。当前同OWASP48实际外部对照只有CodeQL、Bandit、阿里Open Code Review；独立Scout是平台内部消融，不算另一个官方竞品。

| 对照类型 | 当前覆盖 | 是否足够 | 需要补充 |
| --- | --- | --- | --- |
| 传统静态分析 | CodeQL、Bandit实跑；Semgrep CE登记 | 首轮够，正式常规比较仍缺Semgrep | P0：冻结并运行Semgrep CE。仅Bandit不能代表跨函数/跨文件静态分析 |
| 普通LLM/Agent | 平台Scout消融、阿里OCR实跑 | 工具对照已有，受控独立Agent组不足 | P0：真正独立运行同模型普通源码审计Agent，对齐工具权限和阅读预算 |
| AI+静态混合分析 | IRIS、SemTaint、QRS、QLPro登记/材料 | 方法覆盖有，尚无适配当前任务的官方同榜实跑 | P1：优先审查JS相关SemTaint、Py/JS可适配方法。Java/C结果与方法重实现分别报告 |
| 业务逻辑/访问控制 | ABSENTIA专项已计划 | 数据任务合适，不能称竞品复现完成 | P0：BAC-Bench固定源码和裁决；等官方检测器发布再复现 |
| QL生成 | QLCoder/CQLLM/ARQ等 | 文献较齐，实测独立外部生成器不足 | P0：独立Py/JS正反例与参考QL；再接入CQLLM可复现部分。QLCoder作为强方法参考/未来语言专项 |
| 代码修复 | 修复基准和联合oracle候选 | 外部修复Agent缺口最大 | P0：OpenHands同任务修复；直接LLM修复受控组；P1：SWE-agent或mini-SWE-agent |
| 工业商业产品 | Cyfendo自报；Frame/VyQL官方参照 | 不足以代表工业产品，现阶段也非必需 | 可选：SonarQube、CodeRabbit Security；获取许可/入口后再做同任务，先保持报告参照 |

### 必须对齐版本和产品能力

- Semgrep CE与Pro不能混名。官方说明CE主要在单函数内分析；跨函数/跨文件分析属于不同能力范围。[官方对照](https://staging.semgrep.dev/products/semgrep-vs-ce/)
- SonarQube Community Build有Py/JS规则，但注入漏洞的SAST污点引擎在Developer等商业版；若加入要登记具体edition和规则，不能只写“SonarQube”。[官方版本说明](https://www.sonarsource.com/products/sonarqube/downloads/)
- RepoAudit官方目前支持多语言，但示例bug类型是NPD/MLK/UAF，不能因“支持Python”直接放到Web SQLi/授权任务榜单。[官方仓库](https://github.com/PurCL/RepoAudit)
- OpenHands是修复方向很重要的缺失对照：[Vul4Py](https://arxiv.org/abs/2608.00692)已使用它。严格论文复现要固定作者实际runtime版本；截至本次核查，`OpenHands/OpenHands`主要是Agent Canvas，实际Agent SDK在[software-agent-sdk](https://github.com/OpenHands/software-agent-sdk)。不能直接拉最新主分支冒充论文版本。
- [OpenHands vulnerability-fixer演示](https://github.com/OpenHands/vulnerability-fixer)用Trivy扫描/报告输入，和源码根因修复任务不同；优先接入真正的Agent运行协议。

### 新近工业报告参照

[CodeRabbit Security报告](https://www.coderabbit.ai/blog/security-agent-benchmarks)发布于2026-10-06，描述100漏洞/94仓库测试床，并列CodeRabbit、Devin、Codex Security Plugin与Claude Security。表中对比是其内部开发切片的已知目标找回率，明确不测精确率或修复质量。

这份报告可补充工业对照视野，但属于厂商自报，不能把其数字放入当前OWASP48统一成绩列，也不能写成我们已复现这些产品。开放源码材料的公平实跑优先于堆叠自报排名。

## 3. 建议的最小充分对照组合

1. **通用发现**：CodeQL、Bandit（Python子集）、Semgrep CE、阿里OCR、同模型独立普通Agent、当前平台；真实项目与OWASP分开报告。
2. **规则生成**：NoRAG、BM25/向量/混合检索受控消融 + 一个可复现外部生成方法；检索相关性与最终QL可用性分别测。缺乏适配语言的官方工件时，先披露缺口。
3. **修复**：同模型直接LLM、OpenHands、当前语义修复；预算允许再加SWE-agent。所有组在同一已校准安全+业务oracle上评分，不把纯语法检查计作成功。
4. **专项**：ABSENTIA访问控制任务先准备；IRIS/QLCoder语言专项与KeaRepair/AgenticRepair方法研究按各自准入条件推进。

这个组合可以回答“哪些工具类型受益、机制是否有效、代价是多少”。进一步增加商业产品和新模型是扩展项；同任务、独立金标和真实执行是当前更紧迫的缺口。

本次完成联网核查、候选登记和书目元数据修正，没有安装竞品、运行模型基准或启动目标服务。
