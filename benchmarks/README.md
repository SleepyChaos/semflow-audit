# 测试数据集与基准论文索引

这里集中保存测试输入、基准论文、评测协议、实验计划与历史结果；代码审计方法研究另见 [research](../research/README.md)。

漏洞发现最新结果入口：[代码审计测试现状与 RealVuln 核查（2026-11-02）](reports/audit-testing-status-20261102.md)。
RealVuln 最新保留实验为 10-14 六组消融；11-02 为历史证据重算日期，并未新增模型测试。
按项目分析与论文机制假设见 [RealVuln 发现优势与消融证据](reports/realvuln-discovery-advantages-20261102.md)，附26项目与252个新增命中明细。
三部分研究的新入口：[代码审计机制诊断](reports/audit-mechanisms-diagnosis-20261102.md)与[互补发现／前提复审／反馈补证协议](experiments/audit-mechanisms-protocol-20261102.md)。已完成历史诊断和DVGA四组输入预检，尚未运行新模型实验。
后续本地改进与原理解析见[三份机制详解](../design/audit-mechanisms/README.md)：有效不足的受限补证已接入并增加工程回归；服务器未由本轮更新，RealVuln新模型效果尚未重测。

| 目录 / 文件 | 内容 |
| --- | --- |
| [datasets/](datasets/README.md) | 39 个可验证、可离线恢复的公开数据压缩包 |
| [dataset-notes/](dataset-notes/README.md) | 数据集作者说明及使用范围 |
| [papers/](../research/papers/README.md) | 发现、修复与规则基准论文；完整论文表统一索引 |
| [catalog/](catalog/discovery.md) | [发现](catalog/discovery.md)、[修复](catalog/repair.md)、[规则](catalog/rules.md)材料目录及机器清单 |
| [test-programs/](test-programs/README.md) | 按功能和测试意图划分的材料与结果 |
| [testing/](testing/README.md) | 项目测试方案、Word/HTML说明和不可变版本收据 |
| [experiments/](experiments/README.md) | 正式实验协议、断点与既有实验结果 |
| [reports/](reports/chain-completion-20261009-results.md) | 链路补测、消融、能力边界与失败记录 |
| [evaluation-protocol.md](evaluation-protocol.md) | 三方向评测协议与答案隔离要求 |
| [manifests/](manifests/repository-datasets.json) | 数据包、逐成员 SHA-256、来源、过滤与排除记录 |

从仓库根目录校验数据：

```sh
python3 system/scripts/benchmarks/archive_research_materials.py
# 在干净 checkout 中恢复到 benchmarks/raw、evaluator-only、model-inputs
python3 system/scripts/benchmarks/archive_research_materials.py --restore
```

展开的 `raw/`、`evaluator-only/`、`model-inputs/` 是本地实验输入，由 Git 忽略；可发布副本在 `datasets/`。标签、修复答案和 PoC 必须与模型输入隔离，不能直接作为 RAG 材料。历史报告中的版本和“当前”均指报告当时，不代表今天的默认配置。迁移前路径见[清单](../design/repository-file-map.json)。
