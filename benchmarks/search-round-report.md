# 三个方向首轮检索完成报告

日期：2026-10-05。已完成漏洞发现、QL 规则生成、修复准确性三个方向的一轮检索与一手来源核查。没有为凑材料把未公开、未下载或语言不适配的项目算作已可运行基准。

## 1. 总体交付

- 三份方向清单（Markdown + JSON），共 29 个材料/任务候选条目、24 篇论文或技术报告条目。条目包含方法参考和重叠来源，**不是 29 个互相独立的可运行数据集**。
- 本地约 292 MB 材料；`papers/` 有 18 个 PDF 文件，包含 QLCoder 同一论文的两个版本，不能说成 18 篇独立论文。其他论文有 HTML 或已核实的原文链接。
- 保留 28 个通过结构/载荷或 ZIP CRC 检查的归档文件，6 个真实 JS 项目各有修复前后源码快照。6 个标签目标文件存在、行号处于原版文件范围内；根因与测试 oracle 仍待校准。
- 逐文件 SHA256/字节数清单、下载失败记录、材料许可与固定版本、评测协议。没有把第三方答案导入生产 RAG。

文件完整性检查仅证明文件可读；PDF 只检查头部，归档检查不证明标签正确或测试能运行。新脚本通过 Ruff。没有运行模型、目标服务、漏洞利用或 GUI 测试。

## 2. 漏洞发现：已找到较完整的组合

| 材料 | 适合验证 | 实际状态 |
| --- | --- | --- |
| [OWASP Python](https://github.com/OWASP-Benchmark/BenchmarkPython) | 标准正负例、CWE 检出及误报 | 完整源码与 1,230 行答案（452 正、778 负、14 类）已保存；需去标签与基线适配 |
| [RealVuln](https://github.com/kolega-ai/Real-Vuln-Benchmark) | 全项目业务逻辑与一般漏洞 | 已保存版本元数据、Flask/DVNA 两个完整目标项目；不是全部 140 项目 |
| [VulnGym](https://github.com/Tencent/VulnGym) | Agent 主动取证、入口/危险操作/路径 | 408 入口标注、393 人工确认已保存；完整目标仓库尚未收齐 |
| [SastBench](https://github.com/RivalSecurity/sastbench) | AI 复审真假告警 | 2,737 条原始记录已保存；是 triage，不用于从零发现召回 |
| OpenSSF 衍生配对候选 | 自然 CVE 的跨文件发现、复扫 | 新 6 个 JS 项目双快照已保存；旧 pilot 仓库已排除，完整暴露审计待做 |

补充近期来源：[VLoc Bench 技术报告](https://cisco-foundation-ai.github.io/vulnerability-localization-benchmark/technical-report.pdf) 适合源码搜索/文件定位；[VEX-Bench](https://arxiv.org/abs/2609.08040) 适合给定依赖漏洞的可达性、配置和环境复审。两项在线一手来源已核查，本轮本地下载因 SSL 连接超时失败，未获取其完整项目。

**建议：** 主测试用标准正负例 + 自然项目；VulnGym/VLoc 另测证据和定位，SastBench/VEX 另测复审。用定位分数代替最终漏洞正确率会掩盖错误。

## 3. QL 生成：论文已找到，现成适配集仍有缺口

直接相关来源包括 [QLCoder（ICLR 2026）](https://openreview.net/forum?id=J91IKwJrqv)、[IRIS（ICLR 2025）](https://arxiv.org/abs/2405.17238)、[国内 CQLLM（2026）](https://doi.org/10.3390/app16010517)、[QRS（2026）](https://arxiv.org/abs/2602.09774) 与 [2026-09 自动查询生成研究](https://arxiv.org/abs/2609.10412)。这些论文 PDF 均已保存。

QLCoder 框架、任务索引和作者输出已下载，但主要是 Java/C；CQLLM 已取 Python QL ZIP、查询、提示 CSV 和测试工作簿，尚未转换成经核实的独立隐藏集。IRIS 只保存固定版本目录元数据；自动查询生成研究的复制包 ZIP 为 0 字节，明确记为下载失败。

**首轮没有找到能直接覆盖本平台 Python/JS 三输入流程、又同时具备完整源码、独立 gold、隐藏正负例和外推任务的现成标准 QL 集。** 这不意味着此类材料不存在，只代表本轮未核实到。

可行安排是用有官方来源的真实项目建立衍生任务，分别测编译、真实目标命中、隐藏正例、隐藏安全负例与跨项目外推；将“检索资料是否合用”和“查询是否检测正确”拆开。检索相关性需要单独人工标注，不能只用最终生成成功倒推检索优劣。[CodeRAG-Bench（NAACL Findings 2025）](https://aclanthology.org/2025.findings-naacl.176/) 可参考其评测思路，但它不是 QL 标准答案库。

## 4. 修复准确性：任务有，联合 oracle 要校准

| 材料 | 实际内容 | 验证边界 |
| --- | --- | --- |
| [PatchEval](https://github.com/bytedance/PatchEval) | 1,000 条任务 JSON；Python 404、JS 300、Go 296 | 只有 176 条填写非空单测命令；230 容器镜像未下载。含官方修复答案，不能整项传给模型 |
| [Vul4Py](https://github.com/tabudz/vul4py) | 100 条 Python 索引与 harness | 脚本允许缺失/skip 功能测试（999）成为 plausible，需按本项目严格标准重校准 |
| [双 oracle 复制包](https://zenodo.org/records/21645415) | 小型功能与安全测试材料 | 旧 8 个 Python/JS 示例已测，仅属开发材料，不能当新隐藏评测 |
| [EduCollab](https://github.com/Hahappyppy2024/EmpricalVDR) | 两个 Py/JS 业务项目选取的 197 文本文件中 188 通过 Git blob 核对，9 缺失 | 不是完整快照；测试文本适合研究权限、业务功能保持，但需要服务的部分未执行 |

新方法参考：[PredicateFix（北大/中兴，ICSE 2026）](https://doi.org/10.1145/3744916.3773159) 用分析谓词连接缺陷与知识范例，其 [Figshare 地址](https://doi.org/10.6084/m9.figshare.26956228) 已从论文确认，复制包尚未获取；[SEC-bench（NeurIPS 2025）](https://github.com/SEC-bench/SEC-bench) 主要面向 C/C++，先作环境和验证流程参考，本轮数据未下载。

**首轮仍未找到可以直接免校准地证明“全部业务语义保持、根因已修复且未引入新漏洞”的 Py/JS 通用基准。** 后续只能在已覆盖的安全和业务合同上作结论，未运行或缺失的测试为未知，静态复扫通过不等于根因验证成功。

## 5. 下一步建议

本轮收集到此结束。后续先执行材料暴露审计、去标签、测试完整性校准，再冻结三份任务集和确定性基线；不要立即对全部原始材料启动模型批量测试。详细对照、指标、消融和速度测量见 [评测协议](evaluation-protocol.md)。

新增下载遇到跨多个域名的 SSL 连接超时，已停止反复尝试，失败 URL 见 `manifests/local-round-two-downloads.json`。没有找到公开复制包或无法适配的材料保留链接与原因，不以替代小例伪装成正式基准。
