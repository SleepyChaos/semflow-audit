# 测试方案资料索引

说明版本 2.2；方案 v7；整理日期 2026年10月11日。编号对应正文来源标识。

前三个模块共选用三篇正式基准论文。OWASP 是补充测试项目；竞品论文用于功能对照和扩展比较。

## 1 RealVuln: Benchmarking Rule-Based, General-Purpose LLM, and Security-Specialized Scanners on Real-World Code

[RealVuln: Benchmarking Rule-Based, General-Purpose LLM, and Security-Specialized Scanners on Real-World Code](https://arxiv.org/abs/2604.13764v1)

审计基准；采用 v1 的 26 项目与 796 项标签。

## 2 OWASP BenchmarkPython

[OWASP BenchmarkPython](https://github.com/OWASP-Benchmark/BenchmarkPython)

专项审计；采用 0.1，共 1230 例。

## 3 PatchEval: A New Benchmark for Evaluating LLMs on Patching Real-World Vulnerabilities

[PatchEval: A New Benchmark for Evaluating LLMs on Patching Real-World Vulnerabilities](https://arxiv.org/abs/2511.11019v1)

修复基准；完整 1000 任务，含 230 动态任务。

## 4 QLCoder: A Query Synthesizer for Static Analysis of Security Vulnerabilities

[QLCoder: A Query Synthesizer for Static Analysis of Security Vulnerabilities](https://proceedings.iclr.cc/paper_files/paper/2026/hash/2adf01ab15adde8820622f7f24bd516b-Abstract-Conference.html)

规则生成唯一正式基准；ICLR 2026，共 176 项 Java CVE。

## 5 用户提供的竞品材料

用户提供的竞品材料

两份 DOC 和一份论文 PDF，保留原目录及原文。

## 6 LLM-based Vulnerability Detection at Project Scale: An Empirical Study

[LLM-based Vulnerability Detection at Project Scale: An Empirical Study](https://arxiv.org/abs/2601.19239v2)

竞品研究材料，对应原文件 证据1.pdf。

## 7 RepoAudit: An Autonomous LLM-Agent for Repository-Level Code Auditing

[RepoAudit: An Autonomous LLM-Agent for Repository-Level Code Auditing](https://arxiv.org/abs/2501.18160v1)

竞品论文；实现资料见官方仓库 https://github.com/PurCL/RepoAudit。

## 8 QLPro: Automated Code Vulnerability Discovery via LLM and Static Code Analysis Integration

[QLPro: Automated Code Vulnerability Discovery via LLM and Static Code Analysis Integration](https://arxiv.org/abs/2506.23644v3)

竞品研究材料；作者已提示实验数据存在错误，不作为正式成绩基准。

## 9 Antiproof: Synthesizing Vulnerability Detectors and Proofs of Exploitability

[Antiproof: Synthesizing Vulnerability Detectors and Proofs of Exploitability](https://arxiv.org/abs/2607.12316v1)

竞品论文；涉及检测器生成和可利用性验证。

## 10 OpenAnt: LLM-Powered Vulnerability Discovery Through Code Decomposition, Adversarial Verification, and Dynamic Testing

[OpenAnt: LLM-Powered Vulnerability Discovery Through Code Decomposition, Adversarial Verification, and Dynamic Testing](https://arxiv.org/abs/2606.19149v2)

竞品论文；涉及漏洞发现与动态验证。

## 11 Semgrep CE 官方仓库

[Semgrep CE 官方仓库](https://github.com/semgrep/semgrep)

开源规则扫描能力。

## 12 Alibaba OpenCodeReview 官方仓库

[Alibaba OpenCodeReview 官方仓库](https://github.com/alibaba/open-code-review)

AI 审查与取证反思能力。

## 13 GitHub Security and quality AI features

[GitHub Security and quality AI features](https://docs.github.com/en/enterprise-cloud@latest/code-security/responsible-use/security-and-quality-ai-features)

CodeQL 与 Copilot Autofix 产品组合。

## 14 Semgrep Autofix public beta

[Semgrep Autofix public beta](https://semgrep.dev/blog/2026/semgrep-autofix-public-beta/)

平台 AI 修复产品。

## 15 About CodeQL

[About CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/)

CodeQL CLI 静态查询和路径分析。

## 16 Semgrep Rule-defined autofix

[Semgrep Rule-defined autofix](https://docs.semgrep.dev/writing-rules/rule-defined-fix)

规则中定义的代码替换，与平台 AI Autofix 分开。

## 17 Semgrep Agentic Workflows

[Semgrep Agentic Workflows](https://semgrep.dev/blog/2026/introducing-semgrep-agentic-workflows-automate-deep-vulnerability-hunting-at-scale/)

平台主动漏洞发现工作流。

## 测试集与实现入口

- [RealVuln 作者仓库](https://github.com/kolega-ai/Real-Vuln-Benchmark)，范围以论文 v1 为准。
- [PatchEval 作者仓库](https://github.com/bytedance/PatchEval)与[官方任务集](https://huggingface.co/datasets/ByteDance/PatchEval)。
- [QLCoder 作者仓库](https://github.com/neuralprogram/QLCoder)，正式论文采用 CodeQL 2.22.2。

资料包内的原始 README 独立保存。纸面目标、论文版本及 README 的固定源码版本见测试集范围说明。
