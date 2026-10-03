# 竞品与测试材料清单

核实日期：2026-10-03。当前平台正式比较范围是 Python、JavaScript/TypeScript；各工具必须保存版本、规则集、分析范围和原始输出。材料保存在被 Git 忽略的 `artifacts/research-materials/`，不把第三方代码或论文附带的结果当成本平台运行结果。

## 1. 竞品选择

| 竞品/基线 | 比较目的 | 实验约束 |
| --- | --- | --- |
| [CodeQL](https://codeql.github.com/) 原始固定查询套件 | 底层 SAST 基线；衡量 AI 复审和新规则带来的增益 | 与平台使用完全相同 CLI、query pack、完整快照；分开记录提库与分析耗时。遵守 CodeQL 使用条款。 |
| [Semgrep CE](https://github.com/semgrep/semgrep) | 模式/单文件分析基线；Python 与 JS 同场比较 | 本次官方 PyPI 版本为 1.179.0；引擎 LGPL-2.1-or-later。CE 和商业跨文件引擎分开列，不以 CE 代表全部产品。 |
| [Bandit](https://github.com/PyCQA/bandit) | Python 常见危险 API 与 AST 插件基线 | 本次官方 PyPI 版本为 1.9.4，Apache-2.0；使用隔离环境，不修改应用依赖。仅比较 Python。 |
| [Alibaba Open Code Review](https://github.com/alibaba/open-code-review) | 国内 LLM Agent 审计与候选评论复审对照 | 固定模型、temperature、上下文/token/工具调用预算；分别评估 diff review 与 full-file scan，不混淆输入范围。源码固定 `a758d9cbfb689937c7857ad64b2dd66adb58c0c2`，Apache-2.0。 |
| 相同模型的直接审计/直接修复 | 控制模型因素，隔离平台流程的作用 | 同一输入、相同模型版本与总预算；禁止将人工/scripted patch 当成模型生成能力。 |
| [IRIS](https://github.com/iris-sast/iris) | 方法层面的神经符号比较 | 目前主要 Java，不作为本平台 Python/JS 实测主表；用其 source/sink 建模方式讨论方法差异。 |

阿里的官方项目名称已核实为 **Open Code Review**。其 hybrid architecture 指确定性流水线与可使用工具的 LLM Agent；自然语言审查规则不能直接等同 CodeQL 编译后执行的数据流查询。此前“纯 LLM 工具”的说法应收紧为：主要缺陷判断由 LLM 做，流程、取证工具和输出结构包含确定性逻辑。[官方说明](https://github.com/alibaba/open-code-review)

Semgrep 维护的规则集与引擎许可证不同。官方规则从 2024 年起受 Semgrep Rules License 限制；本项目不能把它们默认作为可再发布组件。做内部基准时记录具体规则授权；若使用自建规则，表头必须标为“Semgrep CE + 自建规则”，不声称完整商业产品效果。[规则许可说明](https://semgrep.dev/blog/2024/important-updates-to-semgrep-oss/)

## 2. 已实际收集的材料

全部文件逐项 SHA256、字节数、来源 URL、固定 revision 和下载状态见 `artifacts/research-materials/manifest.json`。该清单保留失败记录；不存在的 `LICENSE.md` 备用路径不代表许可证缺失，实际 `LICENSE` 已下载。上游模块没有在宿主被导入或执行；复制包选出的8个Python/JS无依赖小例已在受限Docker中完成双oracle校准，结果见benchmark-results.md第8节。

| 材料 | 本地文件 | 实际内容/用途 | 许可与限制 |
| --- | --- | --- | --- |
| [OpenSSF CVE Benchmark](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | `ossf-benchmark.tar.gz` | 固定 `91c59fd54b2b768c0f310bb0027d2ac59cdf74d4`，223 个 CVE 元数据 JSON；含 pre/post commit、漏洞文件/行与 CWE；用于真实 JS 回归对照 | benchmark MIT；被引用的各项目保留各自许可。旧 CVE 作为标准材料，2026 论文作为方法引用。 |
| OpenSSF 真实 JS 子集 | `js-real-cve/` | 3 项 CVE 的漏洞/修复源文件、label.json 与许可证；CVE-2017-1000427（URL 校验）、CVE-2017-16114（ReDoS）、CVE-2018-16487（原型污染） | marked、lodash 许可证已保留；这是单文件配对材料，不能宣称已下载完整项目或证明跨文件召回。 |
| [AACR-Bench](https://huggingface.co/datasets/Alibaba-Aone/aacr-bench) | `aacr-dataset.json`、`aacr-README.md` | 固定 `47be1d6df1e7faf222cf531587772d92f79fe6b2`；2,145 条评论真假标签 | Apache-2.0 数据卡；输入包含上游 PR 路径/commit，代码快照需单独获取许可。 |
| AACR 当前语言子集 | `aacr-python-js-ts.json` | Python 151、JS 141、TS 422，共 714 条：531 正确评论、183 错误评论；适合复审接受/拒绝/弃权的质量评估 | 沿用原数据许可；不是完整漏洞清单，不直接用于漏洞召回率。 |
| [Vul4Py](https://github.com/tabudz/vul4py) 索引 | `vul4py.csv`、`vul4py-README.md` | 固定 `2649d7b89e796738ebc2bc3fa9480dff5ae15898`；100 个 Python CVE/GHSA 与修复 commit 索引 | GitHub 未看到独立 LICENSE；仅本地研究参考，不宣称可再发布。完整快照与 oracle 尚未下载/执行。 |
| [Execution-calibrated patching 复制包](https://zenodo.org/records/21645415) | `execution-patching-reproduction.zip`、`execution-patching-README.md` | 2026-07-28 归档，1,842,349 字节；74 文件，含 JS/Python/Go 小型 oracle 与作者历史实验 SQLite | Zenodo CC BY 4.0；不是 Vul4Py。作者运行结果不能写成本平台结果。 |
| 复制包的 oracle 例源 | `execution-patching-examples/harness/oracle/examples/` | `py_benchmark.py`、`js_benchmark.py`、`path_traversal.py` 等纯文件提取；为修复的安全性与功能性双 oracle 设计提供材料 | 8个Python/JS无依赖小例已在隔离验证器各运行3轮；其他例源未运行，仍需核实输入、期望与依赖。 |
| 阿里竞品源码说明 | `ocr-README.md`、`ocr-LICENSE` | 固定源码说明和 Apache-2.0 许可证 | 此前已本地构建并运行 preview/delegate；本轮未重新安装，未执行 OCR 内置真实模型评测，不能沿用官方性能宣传作为对比结果。 |

复制包主 ZIP 的 SHA256：`daef48a2df80b798471d844578c4efc7b925819ad633e182d33d1dc52e073a62`。Vul4Py CSV SHA256：`38e3b3f595bcd0ebc7a3a7bbc5200026eee71ab45ff6b808b6ff5e8c39b17547`。

## 3. 新材料如何接入实验

1. **第一层：小型功能烟测。** 使用本项目自建 Python/JS 漏洞与安全对例，重复 3 次，记录原始 SARIF/JSON、冷暖时间、失败与实际 source hash。样本少，不能推广为真实世界准确率。
2. **第二层：真实修复配对。** OpenSSF 先选择 20–30 项不同 CWE，完整下载 pre/post 项目并保留许可；逐项确认根因位置及修复差异。修复后未报告目标漏洞才表示识别官方修复，不代表整个快照安全。
3. **第三层：AI 复审。** AACR Python/JS/TS 714 条按仓库切分开发/测试，过滤安全类评论形成单独子集。分别报告全评论正确性与安全评论正确性；不把性能/可读性评论混入安全漏洞主指标。
4. **第四层：修复正确性。** 优先适配复制包的 Python/JS oracle，再挑 Vul4Py 有可信 baseline/exploit tests 的 CVE。必须先确认原版正常用例通过、安全攻击失败，官方修复两类用例都通过，再评估平台 diff。
5. **第五层：RAG 规则。** 知识库只含通用 CodeQL API、漏洞机制与训练项目信息；测试项目的官方 patch、预期答案、生成规则与 positive fixture 不得进入检索库。按仓库与 CVE 家族隔离，加入保留语义的 API 包装/参数顺序变化及安全 sanitizer 负例。

同一修复提交的配对文件可能仍有其他漏洞。用“目标根因 + 文件/位置 + CWE”进行匹配；无完整标注时其他告警列为人工待判断，不能全部判 FP。漏洞缺失的安全项目也需要确认 ground truth，不能以扫描器没报警来标安全。

## 4. 适合继续跟踪的近期标准材料

| 材料/论文 | 时间 | 当前价值 | 可得性结论 |
| --- | --- | --- | --- |
| [AACR-Bench: Evaluating Automatic Code Review with Holistic Repository-Level Context](https://arxiv.org/abs/2601.19494) | 2026 | 国内阿里团队参与；仓库上下文与真假评论复审 | 官方 HF 数据已下载；源代码上下文需要 PR 快照。 |
| [CrossCommitVuln-Bench](https://arxiv.org/abs/2604.21917) | 2026-04，arXiv 页面称 AIware 2026 接收 | 15 个真实 Python 跨提交漏洞；说明只看 diff 的锚点局限 | 已找到官方 motornomad/crosscommitvuln-bench；固定版本元数据与原始15项论文集已归档，见下面的早期讨论材料复核。 |
| [SecJS Benchmark](https://github.com/SecJS-Vuln-Benchmark/SecJS-Benchmark) | 当前官方 artifact | JavaScript 项目级漏洞/修复快照与标签采集框架 | Apache-2.0 框架；README 明确 ArenaJS 数据未随仓库发布，不声称数据已经下载。 |
| [SecurityEval](https://github.com/s2e-lab/SecurityEval) | 2022 标准材料补充 | 小型 Python CWE 示例；主要原任务是代码生成安全评估 | 最新 README 为 121 prompts/69 CWE，而论文原版 130/75；许可未明确，本轮不下载为主材料，不用作2025/26主引用。 |

不要为满足“论文新”而把旧成熟基准全部排除。建议方法与竞品文献主要采用 2025/2026，数据则采用近期真实 CVE 与成熟公开配对基准，清楚列出年代、选样标准与泄漏控制。


阿里已有本地部署记录：`../outputs/open-code-review-demo.md`。源码与二进制在 `../work/open-code-review/`，此前实际执行了 `version`、`delegate preview`、`delegate rule app.py`、`scan --preview --format json`。文件选取/规则解析是 CLI 真实输出，SQL 注入审查文字由当时 Codex 委托完成，不是 OCR 内置 LLM 的正式扫描结果。


## 5. 回顾最早论文/测试讨论后的补充核实

早期提过的四个基准已重新核实。实际材料位于 `artifacts/research-materials/early-discussion/`，固定 HEAD 版本为下表提交，而不是未经固定的 `main`；最新版与论文原始版本分开写。

| 基准与论文 | 当前官方版本/范围 | 已收集与适用链路 |
| --- | --- | --- |
| [SastBench](https://github.com/RivalSecurity/sastbench)，[2026 论文](https://arxiv.org/abs/2601.02941) | `b8d95b7720491b21d039b7504999577ba7ebb12b`；Apache-2.0；多语言 SAST 告警 triage | README、LICENSE、`data/sastbench-v0.1-original.json`：实际解析 2,737 条（299 TP、2,438 FP）。已按含 Python/JS/TS 文件位置提取候选子集1,313条（90TP/1,223FP），混合语言项仍需人工筛选、按repo切分；这是候选真假复审数据，不是新漏洞发现召回数据。 |
| [RealVuln](https://github.com/kolega-ai/Real-Vuln-Benchmark)，[2026 论文](https://arxiv.org/abs/2604.13764) | HEAD `7a710251f55c17d32d3adcb13d37468e2e3b9e4a`，manifest 内 benchmark **3.1.0，2026-09-10** / ground_truth **3.0.0**（README/CHANGELOG仍显示3.0.0/2026-09-02）；140 repo（66 Python、74 TS/JS），4,138 漏洞、280 FP traps、176 non-scoring。框架 Apache-2.0，数据发行需核对各来源许可 | README、LICENSE、CHANGELOG、benchmark manifest 与 Flask/DVNA 两份 ground-truth。早期“26 Python/796标签”是原论文 v1，不代表最新版；3.0 TS/JS 尚无FP traps，需另补安全负例。优先用于项目级审计召回与业务逻辑漏洞验证。 |
| [Tencent VulnGym](https://github.com/Tencent/VulnGym)，[2026 论文](https://arxiv.org/abs/2608.02001) | **v0.1.4** `cd69f7e163e08485ab5496115ae03439cda6e27e`；CC BY 4.0；184 advisories、408 entry chains，实际文件393条 verify=1 | README、LICENSE、SCHEMA、entries/reports JSONL。人工确认子集适合主动取证：检验 entry point→critical operation→trace 是否对应实际代码；多语言项目要按文件/完整项目语言筛选，不能把全部408当Python/JS。 |
| [CrossCommitVuln-Bench](https://github.com/motornomad/crosscommitvuln-bench)，[2026 论文](https://arxiv.org/abs/2604.21917) | HEAD `e544e645fe164d62e5cbd5241ad49707ea786c73`；annotations CC BY 4.0、scripts MIT；论文15个Python CVE，当前扩展55个完整项但新项人工复核未完 | README、DATASHEET、两份许可与原论文15项annotation。适合验证早期增量锚点问题；当前平台上传完整快照，不宣称已实现跨提交威胁图。扩展项单列探索集，不能混入15项论文主集。 |

RealVuln 的 F3 强调召回，与本平台低噪声复审目标不同：同时报告 precision/recall/F1/F3，不能只取最有利的一个数字。其“未匹配告警一律算FP”的默认规则可能惩罚真实的新发现；主表保留原基准评分，另提供盲审复核表，不能直接改ground truth后覆盖原分数。VulnGym trace 与 CrossCommit rationale 是评价标签，只交给评测器，不放进模型输入或 RAG 库。

版本一致性提醒：RealVuln同一固定commit的README版本3.0.0与manifest benchmark_version=3.1.0不同；数据量一致，ground_truth_version=3.0.0。实验必须引用manifest和固定commit，报告这一元数据差异，避免把文档展示版本当唯一版本来源。
