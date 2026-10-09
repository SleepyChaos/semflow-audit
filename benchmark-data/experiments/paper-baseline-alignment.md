# 论文作者基准与本平台结果对齐

日期：2026-10-05。状态：作者分数已核对，本平台[首轮校准结果](calibration-results.md)已完成；正式同榜成绩仍待门槛对齐。本文只读取本地已收集 PDF，不运行模型或目标项目。主要结果表已提取，并以渲染页面核对；详细的 **8 篇论文、90 行作者结果、PDF SHA256、页号和表号**见 [JSON](paper-baseline-alignment.json)。页号均为 PDF 物理页。

## 1. 先明确怎样才算“提升”

| 等级 | 使用条件 | 当前情况 |
| --- | --- | --- |
| `direct` | 任务 ID/源码、允许输入、评分、分母已一致；可报告同榜差值 | 当前没有已满足项 |
| `reproduction_required` | 方向一致，需冻结作者材料，在同一子集重跑或重评分 | RealVuln、VulnGym、SastBench、PatchEval、Vul4Py |
| `context_only` | 当前语言、任务或黄金标签不一致，仅方法和量级参考 | QLCoder、CQLLM、IRIS |

可以比较不同模型的完整系统表现，但它不能独立证明“某项设计机制带来提升”。设计机制的因果证据仍应来自本平台同模型、同项目、同预算的控制和消融。论文分数用于外部定位，不能代替本轮基线实跑。

**两个项目得分高于作者整榜，不能称超过论文；修复的语法通过率不能减去双 oracle 修复率；QL 编译率不能减去漏洞检出率。** 作者全榜值和本轮值保留在各自列，只有可比门槛通过后才填差值。相关协议见 [evaluation-protocol](../evaluation-protocol.md)。

## 2. 漏洞发现与复审

### RealVuln：最接近全仓库发现，版本差异必须先解决

来源：[arXiv v1](https://arxiv.org/abs/2604.13764)，本地 `papers/discovery/2604.13764v1.pdf`。

- PDF p.5 Table 2：**v1.0 / 26 个 Python 仓库 / 676 漏洞标签 / 120 FP traps / 796 总标签 / 18 CWE 家族**。
- p.6 §3.4：主表采用 `strict_micro F3`；无输出仓库按漏检处理。官方位置/CWE matcher 与本平台根因级评分须分别保留。
- p.7–8 §4：默认配置静态工具、同一提示的 Agent；目标主体为教育/CTF 应用。作者没有列 CodeQL 成绩。
- 本地冻结的仓库 manifest 是 **3.1.0**，且仅下载 Flask 与 JS DVNA 两个完整目标，不能视为论文 26-Python 的全榜复现。

作者主表（p.10 Table 4，F 值范围 0–100；P/R 范围 0–1）：

| 作者配置 | F1 | F3 | Precision | Recall | 完成项目 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kolega.Dev v0.0.1 | 52.4 | 73.0 | 0.388 | 0.809 | 26/26 |
| Claude Sonnet 4.6 Agent | 60.9 | 51.7 | 0.785 | 0.498 | 23/26 |
| Gemini 3.1 Pro Agent | 60.1 | 51.0 | 0.774 | 0.491 | 24/26 |
| SecLab Taskflow / GPT-5.4 | 13.7 | 8.4 | 0.605 | 0.077 | 26/26 |
| Semgrep 默认配置 | 18.9 | 17.7 | 0.205 | 0.175 | 25/26 |
| Snyk 默认配置 | 21.0 | 17.4 | 0.282 | 0.167 | 25/26 |
| SonarQube Community | 11.8 | 7.1 | 0.611 | 0.065 | 26/26 |

**对齐动作：**先取作者 v1 manifest/标签/原始输出，确认本轮项目和 commit 是否存在；如只测同一小子集，用作者逐项目输出在该子集重新评分。只有当前版本材料时，本轮报告版本内 CodeQL/Agent/双引擎差值，并把作者 v1 表作为背景。

### VulnGym：适合取证路径，但 T1 不是完全无提示发现

来源：[arXiv v1](https://arxiv.org/abs/2608.02001)，本地 `papers/discovery/vulngym-2608.02001v1.pdf`。

- p.3–4：**184 advisories / 408 entries / 23 仓库**；T1 直接提供 advisory 标题、描述与仓库；其他任务会给黄金 EP/CO。
- p.4：EP、CO 同路径且偏差不超过 **5 行**，双端点均匹配才命中 entry。AR 是 advisory 覆盖，ER 是 entry 覆盖，ES 是 trace 编辑相似度，不能称 T1 完整精确率。
- p.5：frontier Table 2 只测 **Hard 31 advisories / 46 entries**。只读工具设置；不能将该分母换成全部数据。

作者 T1 Hard 表（p.5 Table 2，以下都是百分比）：

| Scaffold / 模型 | AR | ER | ES |
| --- | ---: | ---: | ---: |
| Claude Code / DeepSeek-V4-Flash | 9.68 | 6.52 | 3.37 |
| OpenHands / DeepSeek-V4-Flash | 22.58 | 15.22 | 11.63 |
| MiniSWE / DeepSeek-V4-Flash | 16.13 | 10.87 | 7.67 |

**对齐动作：**另建给定 advisory 的路径任务，冻结 Hard 清单、提交和作者 evaluator。平台配置的 `deepseek-v4.1-flash` 不默认等同于作者 `DeepSeek-V4-Flash`。当前只有标注，目标仓库未全部下载；暂无同榜提升结论。

### SastBench：复审真假告警，不是从零发现召回

来源：[arXiv v1](https://arxiv.org/abs/2601.02941)，本地 `papers/discovery/2601.02941v1.pdf`。

- p.4–5 Tables 2–3：**2737 告警 / 299 TP / 2438 近似 FP / 38 语言 / 139 CWE**。输入是给定 CWE 告警分组、位置/函数元数据、指定 commit 仓库；`source` 标签不进入 Agent。
- p.6：主指标 MCC；每模型/架构仅一轮。GPT OSS 因 DSPy 错误仅测子集。

作者成绩（p.6 Table 4）：

| 配置 | Precision | Recall | F1 | MCC |
| --- | ---: | ---: | ---: | ---: |
| Gemini 2.5 Pro / Improved ReAct | 0.169 | 0.582 | 0.262 | 0.148 |
| Claude Sonnet 4.5 / Improved ReAct | 0.140 | 0.722 | 0.235 | 0.110 |
| Gemini 2.5 Pro / Simple ReAct | 0.140 | 0.565 | 0.224 | 0.084 |
| DeepSeek R1 / Simple ReAct | 0.123 | 0.544 | 0.201 | 0.042 |

**对齐动作：**适配平台复审入口，不把独立粗筛输出当 triage。Py/JS 子集需同子集基线或作者逐项重评分；复核负标签来源。JSON 中的 `author_f2` 原样保留，禁止用疑似表格口径错误污染本平台按公式算出的 F2。

## 3. RAG 与 QL 规则生成

### QLCoder：有完整可执行成功标准，但当前 Java 与反馈权限不同

来源：[ICLR 2026](https://openreview.net/forum?id=J91IKwJrqv)，本地 `papers/rules/qlcoder-iclr2026.pdf`；同作品 arXiv 版本不重复计论文。

- p.7：**176 Java CVEs = 111 旧 CVE + 65 新 CVE**，Claude Code / Sonnet 4，CodeQL **2.22.2**，最多 **10** 合成迭代。附录 p.13 又写旧项目可构建 112，清单需核对。
- p.4/7：生成器可取 patch information，validator 反复反馈漏洞版和修复版命中方法；不同于本项目将隐藏修复版留在评测器侧。
- p.8 Table 1：**94/176 查询成功，53.4%，平均 precision 0.631**。成功需查询可用、漏洞版目标命中、修复版无相关误报。
- p.8 Table 2 是另一 **130 shared CVEs** 的 recall 表；不能把它与 176-task success 混为一个指标。

| 作者共享集配置 | Recall % | 平均 Precision | 平均 F1 |
| --- | ---: | ---: | ---: |
| CodeQL | 20.0 | 0.055 | 0.073 |
| IRIS | 35.4 | 0.031 | 0.048 |
| QLCoder | 80.0 | 0.672 | 0.700 |

p.9 Table 4 的 **20-CVE** 消融：完整 success **55%**，去 LSP **25%**，去 Doc/Ref **20%**，去 AST **25%**，无专用工具的 Claude Code **10%**。它支持工具、资料和执行反馈的研究动机；本平台旧 18 次 Py/JS 小测试不能直接与这些百分比排名。

### CQLLM：同 Python 方向，但不能用“告警总量”代表准确率

来源：[Applied Sciences 2026](https://doi.org/10.3390/app16010517)，本地 `papers/rules/cqllm-applsci2026.pdf`。

- p.8：基于官方 Python QL 及增强样本，**3754 微调样本 = 3004 train + 375 validation + 375 test**。
- p.11–12：**54 CWE 类型**数据库，五字段请求与 QL library 限制；execution 是编译和执行完成，CWE coverage 是类型覆盖；没有独立检索相关性标签。
- p.15 结论承认未逐样本标注漏洞位置，所以 `Total_vul` 是待核对告警量，不能作 TP 数或精准检测证据。

作者执行结果（p.15 Table 4，Qwen2.5-coder-7B）：

| 组 | 分母 QL | 可执行 | 执行率 | 作者告警量 |
| --- | ---: | ---: | ---: | ---: |
| CQLLM：微调 + RAG | 321 | 181 | 56.38% | 3930 |
| 仅微调 | 321 | 71 | 22.11% | 1765 |
| 仅 RAG | 298 | 216 | 72.48% | 4755 |

表 2 的同 7B 写 **56.43%**，正文另有 **58.38%**；均保留来源，不挑最高数字。表 4 的仅 RAG 分母又不同，不能视为严格配对提升。当前缺作者完整任务/数据库与精确正负标签，只作方法参照；如做复现，需要补齐并保持微调因素一致。

### IRIS：检测/建模方法参照，不是全文 QL 生成或检索榜

来源：[ICLR 2025 / arXiv v3](https://arxiv.org/abs/2405.17238)，本地 `papers/rules/iris-arxiv-v3.pdf`。

p.7–8：**120 Java CVEs / 4 CWE**；CodeQL **2.15.3**，GPT-4 `gpt-4-0125-preview` 等推断 source/sink 并过滤路径。p.8 Table 1：CodeQL **27/120（22.50%）**，IRIS+GPT-4 **55/120（45.83%）**；平均 F1 **0.076 → 0.177**，平均 FDR **90.03% → 84.82%**。

作者 FDR 基于不完备黄金位置，是近似误报上界，不等于本平台裁决后的真实 precision。当前语言与建模任务不同，只作参考，不能声称本平台超过 IRIS。

**检索缺口：**上述三篇没有提供可直接用于本项目的独立 Py/JS QL 资料相关性黄金标注。BM25、向量、混合优劣仍须分别测 Recall@k/nDCG/MRR、API/版本适配，不能只从最终 QL 分数归因检索优劣。

## 4. 语义辅助修复

### PatchEval：动态榜分母 230，不能除以 1000

来源：[arXiv v1](https://arxiv.org/abs/2511.11019)，本地 `papers/repair/patcheval-2511.11019v1.pdf`。

- p.5–6：**1000 CVEs / 65 CWE / Python、JS、Go** 是等价评测集；只有 **230** 是构建了动态 sandbox 的安全测试集。
- p.7–9：location 组给正确漏洞函数和领域知识；end-to-end 组仍给漏洞描述。正式动态修复指标为安全与 unit 联合通过，LLM-as-judge 另列。
- p.16：Agent 最大 **100** 交互或 **30 分钟**；p.11 §4.5 反馈主设置 **5 轮**，隐藏测试不回流组不能直接对其排名。

作者动态结果（p.9 Table 3 与 p.11 Tables 5–7；分母 230）：

| 配置/输入 | 联合通过数 | 单独安全通过数 | 来源 |
| --- | ---: | ---: | --- |
| Gemini2.5-Pro / location 单轮 | 52 | 58 | Table 3 |
| DeepSeek-R1 / location 单轮 | 44 | 47 | Table 3 |
| GPT-4.1 / location 单轮 | 43 | 51 | Table 3 |
| SWE-Agent+Gemini2.5 / location | 53 | 61 | Table 3 |
| OpenHands+Gemini2.5 / 无 location | 43 | 45 | Table 5 |
| Gemini2.5-Pro / location +反馈 | 122 | 未单列 | Table 6 |
| OpenHands+Gemini2.5 / location +反馈 | 129 | 未单列 | Table 6 |
| OpenHands+Gemini2.5 / 无 location +反馈 | 82 | 未单列 | Table 7 |

本地 1000 项 JSON 和 176 个非空 unit 命令不是经过确认的 230 动态清单，也不保证测试可运行。**对齐动作：**冻结相同动态任务；筛纯单元后在同子集跑基线；双 oracle 实际缺失/skip/超时记 unknown。官方 script 的条件性 unit 判断需与论文联合标准分开披露。

### Vul4Py：最直接的 Python 双 oracle 参照，需要审查实现缺口

来源：[arXiv PDF](https://arxiv.org/abs/2608.00692)，本地 `papers/repair/vul4py-2608.00692.pdf`。

- p.7：**100 CVEs / 60 项目 / 60 CWE**，声称入集要求原版功能通过、安全失败，官方修复版双通过。
- p.9–11：给定 CVE 与官方修复触及的文件/行范围；Agent 还能读取项目、构建与运行测试。Sonnet4 `claude-sonnet-4-20250514`、temperature **0**、最多 **100 steps**；通常 **$3** cap，Trae 没有这个 cap。
- p.11–12：`Sec` 是安全单通过，`Plau` 是联合通过，`Corr` 是人工对照修复意图后的正确数，三者必须分开。

作者结果（p.12 Table 2，分母 100；均值为每实例补丁生成成本和时间）：

| 配置 | Sec | Plau | Corr | 均值秒 | 均值美元 |
| --- | ---: | ---: | ---: | ---: | ---: |
| APPATCH+Sonnet4 | 3 | 2 | 2 | 93 | 0.05 |
| GPT-4o | 0 | 0 | 0 | 7 | 0.03 |
| Sonnet4 直接提示 | 5 | 5 | 4 | 6 | 0.05 |
| OpenHands+Sonnet4 | 51 | 43 | 41 | 490 | 1.32 |
| Trae Agent+Sonnet4 | 33 | 30 | 29 | 5763 | 7.52 |
| SWE-agent+Sonnet4 | 27 | 24 | 22 | 2052 | 1.43 |

**对齐动作：**只选择已校准纯单元任务，匹配同子集再测。本地脚本 `functional_rc=999` 仍可获 plausible 的分支与双 oracle 宣称有差异，平台严格口径不能接受它。论文 Agent 试跑验证与本轮隐藏反馈隔离不同；既报告论文复现口径，也报告严格口径。当前语法/静态复扫成绩不能填 Plau/Corr，更不能据此声称语义修复超过作者。

## 5. 本轮结果表的填法

每个结果保存 `task_manifest_hash / input_permission / model / CodeQL_pack / metric / denominator / status / source_run`。报告分三层：

1. **本平台配对对照**：同任务 CodeQL→双引擎、无检索→检索组、无语义→分层语义组；这是当前最先能确认的效果增益。
2. **作者同子集外部对照**：经版本/评分核对后，作者逐项输出重评分或方法重跑。直接给 TP/FN/FP、通过计数、配对差值及未决项。
3. **作者原表背景**：保留以上值及来源，注明“不在同榜，不计算超过幅度”。

当前只有校准分数，没有本轮正式同榜平台分数，因此全部作者条目的 `improvement_claim_allowed=false`。如后续只完成校准、小批试跑或存在 oracle 缺口，明确报告边界，不把未完成项伪装成零成绩或将论文值搬作本平台实跑基线。
