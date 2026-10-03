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

全部文件逐项 SHA256、字节数、来源 URL、固定 revision 和下载状态见 `artifacts/research-materials/manifest.json`。该清单保留失败记录；不存在的 `LICENSE.md` 备用路径不代表许可证缺失，实际 `LICENSE` 已下载。材料没有被执行或导入为 Python 模块。

| 材料 | 本地文件 | 实际内容/用途 | 许可与限制 |
| --- | --- | --- | --- |
| [OpenSSF CVE Benchmark](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | `ossf-benchmark.tar.gz` | 固定 `91c59fd54b2b768c0f310bb0027d2ac59cdf74d4`，223 个 CVE 元数据 JSON；含 pre/post commit、漏洞文件/行与 CWE；用于真实 JS 回归对照 | benchmark MIT；被引用的各项目保留各自许可。旧 CVE 作为标准材料，2026 论文作为方法引用。 |
| OpenSSF 真实 JS 子集 | `js-real-cve/` | 3 项 CVE 的漏洞/修复源文件、label.json 与许可证；CVE-2017-1000427（URL 校验）、CVE-2017-16114（ReDoS）、CVE-2018-16487（原型污染） | marked、lodash 许可证已保留；这是单文件配对材料，不能宣称已下载完整项目或证明跨文件召回。 |
| [AACR-Bench](https://huggingface.co/datasets/Alibaba-Aone/aacr-bench) | `aacr-dataset.json`、`aacr-README.md` | 固定 `47be1d6df1e7faf222cf531587772d92f79fe6b2`；2,145 条评论真假标签 | Apache-2.0 数据卡；输入包含上游 PR 路径/commit，代码快照需单独获取许可。 |
| AACR 当前语言子集 | `aacr-python-js-ts.json` | Python 151、JS 141、TS 422，共 714 条：531 正确评论、183 错误评论；适合复审接受/拒绝/弃权的质量评估 | 沿用原数据许可；不是完整漏洞清单，不直接用于漏洞召回率。 |
| [Vul4Py](https://github.com/tabudz/vul4py) 索引 | `vul4py.csv`、`vul4py-README.md` | 固定 `2649d7b89e796738ebc2bc3fa9480dff5ae15898`；100 个 Python CVE/GHSA 与修复 commit 索引 | GitHub 未看到独立 LICENSE；仅本地研究参考，不宣称可再发布。完整快照与 oracle 尚未下载/执行。 |
| [Execution-calibrated patching 复制包](https://zenodo.org/records/21645415) | `execution-patching-reproduction.zip`、`execution-patching-README.md` | 2026-07-28 归档，1,842,349 字节；74 文件，含 JS/Python/Go 小型 oracle 与作者历史实验 SQLite | Zenodo CC BY 4.0；不是 Vul4Py。作者运行结果不能写成本平台结果。 |
| 复制包的 oracle 例源 | `execution-patching-examples/harness/oracle/examples/` | `py_benchmark.py`、`js_benchmark.py`、`path_traversal.py` 等纯文件提取；为修复的安全性与功能性双 oracle 设计提供材料 | 尚未运行、不保证可直接接入；先人工核实输入、期望与依赖，再在受限容器适配。 |
| 阿里竞品源码说明 | `ocr-README.md`、`ocr-LICENSE` | 固定源码说明和 Apache-2.0 许可证 | 尚未安装或实测，不能沿用官方性能宣传作为对比结果。 |

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
| [CrossCommitVuln-Bench](https://arxiv.org/abs/2604.21917) | 2026-04，arXiv 页面称 AIware 2026 接收 | 15 个真实 Python 跨提交漏洞；说明只看 diff 的锚点局限 | 本轮核实摘要和提交日期，未找到并下载可固定的数据 artifact，不列为已准备就绪。 |
| [SecJS Benchmark](https://github.com/SecJS-Vuln-Benchmark/SecJS-Benchmark) | 当前官方 artifact | JavaScript 项目级漏洞/修复快照与标签采集框架 | Apache-2.0 框架；README 明确 ArenaJS 数据未随仓库发布，不声称数据已经下载。 |
| [SecurityEval](https://github.com/s2e-lab/SecurityEval) | 2022 标准材料补充 | 小型 Python CWE 示例；主要原任务是代码生成安全评估 | 最新 README 为 121 prompts/69 CWE，而论文原版 130/75；许可未明确，本轮不下载为主材料，不用作2025/26主引用。 |

不要为满足“论文新”而把旧成熟基准全部排除。建议方法与竞品文献主要采用 2025/2026，数据则采用近期真实 CVE 与成熟公开配对基准，清楚列出年代、选样标准与泄漏控制。
