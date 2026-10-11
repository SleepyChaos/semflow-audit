# Semflow Audit 项目测试方案说明

说明版本 2.1    测试方案 v6    2026年10月11日

验证双引擎代码审计、代码修复和规则生成，以完整测试集为目标。

## 1. 功能与多智能体设计

四个 Agent 由 LangGraph 组织协作，分别负责发现、复核、修复和规则生成。

**表1 模块角色与验证目标**

| 模块 | 角色分工 | 验证目标 |
| --- | --- | --- |
| 双引擎代码审计 | CodeQL 静态扫描；ScoutAgent 主动发现；ReviewAgent 取证复核 | 发现更多有效漏洞，降低误报，结论关联真实源码证据 |
| 代码修复 | RepairAgent 根据问题和验证反馈生成、修订源码补丁 | 目标漏洞消除，同时保持正常功能 |
| 规则生成 | RuleGeneratorAgent 基于 RAG 知识生成、修订 CodeQL 查询 | 查询可执行，命中漏洞版本，区分修复版本 |

## 2. 双引擎代码审计测试

RealVuln v1 检验项目审计，OWASP BenchmarkPython 0.1 检验专项准确性。[1,2]

**表2 审计测试内容与作用**

| 测试材料 | 完整范围 | 测试作用 |
| --- | --- | --- |
| RealVuln v1 | 26 个 Python 项目；676 个漏洞标签、120 个误报陷阱，共 796 项标签；18 个 CWE 家族 | 验证项目审计能力、两引擎互补和复核后的误报控制 |
| OWASP BenchmarkPython 0.1 | 1230 例；452 正例、778 负例；14 个类别 | 验证漏洞检出率、误报率和类别覆盖 |

目标是完成两套全量测试，报告 P、R、F1、F3 及分类结果。预期双引擎增加有效发现，ReviewAgent 降低误报并保留正确发现。

**表3 RealVuln 论文对照成绩**

| 作者配置 | P | R | F1 | F3 |
| --- | --- | --- | --- | --- |
| Kolega.Dev v0.0.1 | 38.8% | 80.9% | 52.4 | 73.0 |
| Claude Sonnet 4.6 Agent | 78.5% | 49.8% | 60.9 | 51.7 |
| Semgrep 默认配置 | 20.5% | 17.5% | 18.9 | 17.7 |

来源为论文 Table 4，F1、F3 为百分制；Claude 和 Semgrep 分别完成 23/26、25/26 项目。作者成绩作参考，本项目成绩以实际测试为准。

## 3. 代码修复测试

采用 PatchEval 论文 v1，验证真实 CVE 的补丁是否同时满足安全性和功能保持。[3] 全量目标为 1000 项任务，覆盖 Python、JavaScript、Go 和 65 类 CWE。

其中 230 项具有动态安全 PoC 和功能测试，评价安全与功能联合通过率；其余 770 项评价补丁等价性。两种结果分别报告。预期 RepairAgent 较同模型直接修复提高联合成功率，减少功能破坏。

**表4 PatchEval 论文单次补丁对照成绩**

| 作者配置 | 联合通过 | 通过率 |
| --- | --- | --- |
| GPT-4.1 | 43/230 | 18.70% |
| Gemini 2.5 Pro | 52/230 | 22.61% |
| DeepSeek R1 | 44/230 | 19.13% |
| SWE-Agent 加 Gemini 2.5 Pro | 53/230 | 23.04% |

论文 Table 3，对照采用给定漏洞位置、单次补丁的安全与功能联合通过率。

## 4. 规则生成测试

以 ICLR 2026 正式论文 QLCoder 为唯一基准，验证 RuleGeneratorAgent 的规则生成效果。[4] QLCoder 使用 Claude Code Agent，结合文档检索与查询反馈；完整目标为 176 项 Java CVE 配对任务、42 类 CWE。

**表5 规则生成的成功条件**

| 验证内容 | 判定目标 |
| --- | --- |
| 可执行 | 同一查询在漏洞版和修复版数据库上编译、运行成功 |
| 漏洞命中 | 漏洞版的目标路径经过安全修复区域 |
| 修复版区分 | 修复版不再报告对应的同一漏洞路径 |

同一候选满足三项条件才计成功，成功率的完整分母为 176。论文 Claude Code Agent 加 Claude Sonnet 4 在最多 10 轮下成功 94/176，成功率 53.4%，平均路径精确率 0.631。

预期提高联合成功率，减少无效查询和修复版误报。本方案评价含 RAG 的规则模块整体效果。

## 5. 竞品功能与测试对照

功能范围以所列工具、产品组合和研究实现为准。“有”表示提供，“部分”表示范围有限，“未列”表示公开材料未列出。来源编号见随附资料索引。

**表6 项目与竞品功能范围**

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

本项目按设计能力列示，全量效果待测试验证。RepoAudit 包含 MetaScanAgent、DFBScanAgent。QLPro 修订的是 QL，且作者提示实验数据存在错误，仅作研究参考；Antiproof、OpenAnt 的漏洞验证不等同于补丁验证。

**表7 三个模块的竞品测试对照**

| 模块 | 优先对照对象 | 测试范围 | 比较目标 |
| --- | --- | --- | --- |
| 双引擎代码审计 | CodeQL CLI；Semgrep CE；Alibaba OpenCodeReview | RealVuln 26 项目、796 项标签；OWASP 1230 例 | 检出和误报、引擎增益、复核效果、耗时成本 |
| 代码修复 | Copilot Autofix；Semgrep Autofix<br>内部基线：同模型直接修复 | PatchEval 1000 任务、230 动态任务 | 安全与功能联合成功、可应用补丁、触发覆盖率、耗时成本 |
| 规则生成 | QLCoder<br>内部基线：同模型基础生成 | QLCoder 176 项 Java CVE、42 类 CWE | 查询可执行、漏洞命中、修复版区分、生成成本 |

RepoAudit、OpenAnt、Antiproof 可作审计扩展对照。竞品按共同支持任务比较并列出覆盖率；本项目仍以各模块完整范围为目标。

### 论文与项目来源

[1] RealVuln 论文 v1

[论文原文](https://arxiv.org/abs/2604.13764v1)

[2] OWASP BenchmarkPython 0.1

[项目地址](https://github.com/OWASP-Benchmark/BenchmarkPython)

[3] PatchEval 论文 v1

[论文原文](https://arxiv.org/abs/2511.11019v1)

[4] QLCoder ICLR 2026 正式论文

[论文原文](https://proceedings.iclr.cc/paper_files/paper/2026/hash/2adf01ab15adde8820622f7f24bd516b-Abstract-Conference.html)

完整论文、测试集说明和竞品材料见随附资料索引。
