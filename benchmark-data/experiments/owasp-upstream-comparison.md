# OWASP 上游 Bearer 输出回放核查

日期：2026-10-05。结论：**可机械回放，但输入身份未对齐且有大量扫描失败，不能作为本轮有效竞品成绩；不计算提升或速度差。**

## 1. 来源与工作范围

上游：[OWASP BenchmarkPython](https://github.com/OWASP-Benchmark/BenchmarkPython)。本地固定提交 `f1291485808b66e20ddb6b01b10dc71b3df8c8ba` 包含：

- `results/Benchmark-Bearer-v1.51.1.json`：Bearer 原始输出。
- `expectedresults-0.1.csv`：当前版本的测试标签。
- `scripts/runBearer.sh`：上游运行方式，Docker `scan /benchmark --format jsonv2`，动态拉取镜像。

本轮只解析文件并运行本项目评测器，**没有运行 Bearer、Docker、目标源码或 GUI**。归档输出声明工具为 Bearer **1.51.1**，未附原始扫描 commit、时间、耗时、镜像 digest 或规则配置；不能把下载文件的仓库提交当成当时扫描提交。

详细收据：[upstream-bearer-rescore.json](../../artifacts/research/formal/20261005-calibration-v1/upstream-bearer-rescore.json)。收据保存原文件、CSV、标签、评分器的 SHA256，逐告警输入身份检查、逐文件错误与逐案例诊断。其状态为 `archived_output_replay_completed_input_identity_mismatch`，可比性为 `context_only`。

## 2. 如何读取 Bearer JSON

| 字段 | 本轮解释/使用 |
| --- | --- |
| 顶层 `source` / `version` | 工具名称/版本；不是 benchmark 版本 |
| `findings` | 告警行列表，共 143 行 |
| `errors` | 文件扫描失败列表，共 798 行；必须保留 |
| `cwe_ids` | 工具显式 CWE；只转为规范 `cwe-N` 标签，不做近义映射 |
| `id` | 规则 ID，多告警共享它，不能用它去重整份结果 |
| `filename` / `full_filename` | 仓库相对路径与容器绝对路径；用相对路径对应案例 |
| `line_number` | 主位置；本项目 testcase adapter 不要求黄金行号匹配 |
| `source` / `sink` | 告警内的起止行、列范围；不是额外独立告警。sink 另带 content |
| `parent_line_number` | 父级/上下文位置，不另记命中 |
| `fingerprint` / `old_fingerprint` | 工具结果指纹；current fingerprint 在本文件均唯一，不代表根因黄金身份 |
| `title` / `description` / `documentation_url` | 规则说明，不能取代显式 CWE 或黄金标签 |
| `code_extract` | 原扫描位置的源码片段；仅用于检查输入漂移 |
| `severity` | 工具风险等级，本轮二分类评分不使用 |

143 告警对应 **6 个规则 ID、143 个唯一 fingerprint、133 个不同文件**。主文件+CWE 组合没有完全重复项，但同文件不同 CWE 可以有多条。评测器最后用 testcase ID 的集合归并预测，每个案例只能增加一次 TP/FP，不能按告警数量累加。

## 3. 标签与 adapter 一致性

当前 CSV 与本轮 evaluator-only `owasp-labels.json` 完全一致：**1230 案例，452 正例、778 负例**。匿名文件映射只使用既有 `original_id → task_id/file`，不按标题、源码相似度或语义重新分配答案。

直接调用 [formal_scoring.py](../../scripts/benchmarks/formal_scoring.py) 的 `score_cases`：

1. 从 `filename` 取原案例名，对应既有匿名目标文件。
2. 从 `cwe_ids` 读取数值，转为 `cwe-N` tags。
3. 只给一个主位置；case 文件和**精确 CWE**均匹配才预测该案例为 positive。
4. CWE 不匹配/非案例告警保持 outside，不自动形成另一个 testcase FP；独立真实漏洞审查尚未开展。

特别不能把 weak-random 规则的 **CWE-327** 自行改成 CSV 的 **CWE-330**，也不能把 cookie-http-only 的 **CWE-1004** 改成 secure-cookie 的 **CWE-614**。这些语义/类别匹配需另建预先冻结的评分协议，不能为了这次回放调映射。

## 4. 阻止公平比较的证据

### 扫描错误

798 条错误来自 **798 个不同 Python 文件**，消息均为 `failed to scan file`，并指向 escape sequence 解码失败。当前标签内有 **792 个错误案例：312 正例、480 负例**。其余 6 条为 app.py 或当前标签外案例。

未报错不能自动证明文件已处理，报错更不能当成安全。完整分母机械评分可以展示诊断，但不会把错误案例记录为真实成功 TN。

### 上游输出与当前源码身份不一致

逐告警比较 `code_extract` 与所指当前文件的 `line_number` 源码行：

| 检查结果 | 行数 |
| --- | ---: |
| 文本完全一致 | 10 |
| 文本不一致 | 132 |
| 文件不存在 | 1 |

缺失告警文件为 `testcode/BenchmarkTest01243.py`。扫描错误还涉及 **5 个当前不存在的案例文件**：01231、01234、01235、01239、01241。

部分差异可能来自源码/行号版本变化，但缺失文件和多数片段不一致足以证明当前不能确认同一输入。**两条机械精确 CWE 匹配告警的片段也都不一致。** 没有通过源码文本重新映射 case，这会改变评测身份并引入主观分配。

## 5. 机械回放结果：仅用于适配诊断

| 诊断范围 | 案例数 | TP | FP | TN | FN | 解释 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 全部当前标签直接套 adapter | 1230 | 1 | 1 | 777 | 451 | 含大量失败/身份漂移；不是有效检出成绩 |
| 去掉显式错误案例的诊断切片 | 438 | 1 | 1 | 297 | 139 | 无报错也非成功处理证明；仍存在身份漂移 |

143 条原始告警仅 **2 条**满足当前文件名+精确 CWE，归并成 **2 个**预测案例；其余 **141 条**保留为 outside。outside 包含 **4 条非目标文件告警**及 **137 条当前目标文件但 CWE 不匹配告警**，不自动裁决其是否是真实其他漏洞。

JSON 同时保存机械 P/R/F1 数值以保证算法回放完整，但禁止引用为有效榜单或据此称 CodeQL/双引擎超过 Bearer。显式错误案例标记 `unknown_explicit_scan_error`，其余标记“未见显式错误、不能证明处理”。

## 6. 下一步可比比较条件

- 找回 Bearer 原扫描源码提交、相同标签与原始运行收据，再使用同一 adapter 回放；或在本轮固定匿名源码上实际运行固定 Bearer 引擎、镜像/规则。
- 相同源码、标签、评分器和失败口径后才比较准确度；同机相同输入实跑并计时后才比较速度。
- 当前 CodeQL 是匿名去标签源码的本机扫描；Bearer 是身份未核齐的上游历史原源码输出。两者不得填差值，更不是论文同榜提升证据。
- OWASP 官方 scorecard 尚未运行。本回放使用自定义 testcase adapter，不能称官方 OWASP 得分。
