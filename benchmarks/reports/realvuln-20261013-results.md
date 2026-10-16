# RealVuln 论文全 26 项目：单 CodeQL 与综合审计系统

日期：2026-10-13。全部项目已尝试；默认预算下的部分覆盖和未决结果单独保留。

综合系统相对单 CodeQL：TP -5，FP -242，Recall -0.74 个百分点，Precision +38.44 个百分点，F3 -0.15。此结果仅代表本轮冻结实现、模型和预算。

## 两条链路的主结果

分母为论文全部 676 条漏洞；另有 120 条 FP traps。使用官方 strict micro 评分。

| 链路 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 单 CodeQL | 106 | 297 | 570 | 26.30% | 15.68% | 19.65 | 16.34 |
| 综合系统：AI 支持输出 | 101 | 55 | 575 | 64.74% | 14.94% | 24.28 | 16.19 |

综合系统主结果取 Review v12 的 `supported`，是经过产品结构/证据门的 AI 分类，不是本次新增的独立人工确认。未决、证据不足和未检查候选仍保留在产物中，未默认判为误报。

| 辅助口径 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 综合系统：保留所有未决，仅排除已验证误报 | 165 | 257 | 511 | 39.10% | 24.41% | 30.05 | 25.36 |
| 复核前 CodeQL＋粗筛原始并集 | 163 | 375 | 513 | 30.30% | 24.11% | 26.85 | 24.61 |

按黄金标签 ID 配对，最终支持输出新增命中 40 条、失去基线命中 45 条；失去支持可能来自明确排除、证据不足或尚未复核，需要结合每项目记录分析，不能一概称成功过滤。

## 与论文作者结果比较

以下是作者保存输出在本轮相同 26 项目、676 标签上的重评分；没有重新运行这些竞品。传统静态工具、Kolega、Sonnet 和 Gemini 的重评分复现论文主表至显示精度附近。

| 作者已有输出 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| semgrep | 118 | 457 | 558 | 20.52% | 17.46% | 18.86 | 17.72 |
| snyk | 113 | 288 | 563 | 28.18% | 16.72% | 20.98 | 17.42 |
| sonarqube | 44 | 28 | 632 | 61.11% | 6.51% | 11.76 | 7.15 |
| kolega-v0.0.1 | 547 | 862 | 129 | 38.82% | 80.92% | 52.47 | 73.00 |
| claude-sonnet-4-6-agentic-v1 | 337 | 92 | 339 | 78.55% | 49.85% | 61.00 | 51.74 |
| gemini-3.1-pro-agentic-v1 | 332 | 97 | 344 | 77.39% | 49.11% | 60.09 | 50.97 |

论文来源：[RealVuln arXiv v1](https://arxiv.org/abs/2604.13764)，Table 2/4。本轮模型、架构和预算与作者不同，比较的是完整系统表现，不能单独归因到某个机制。

## 完成状态、预算和时间

- CodeQL 成功 26/26；综合阶段结果状态：{'partial': 25, 'completed': 1}。
- Scout/Review 阶段状态：{'completed': 52}；覆盖状态与阶段状态分别记录。未决候选 150 个。
- 独立粗筛检查 112/1168 个非第三方可选窗口；停止原因：{'budget_exhausted': 20, None: 4, 'provider_error': 2}。不能称为所有文件/业务流程均检查完毕。
- 实际模型调用 234 次，输入 2120316 tokens，输出 404227 tokens。服务未提供可靠统一单价，本报告不虚构美元成本。
- CodeQL 抽取＋查询时间合计 455.2 秒；模型阶段合计 2656.2 秒。
- 每项目顺序链路中位数 118.1 秒；项目并发 2，static 输出共享，以上不是产品双引擎并发端到端延迟。两个粗筛阶段因用户中断沿用原 ID 和持久化调用预算恢复；其 wall_seconds 只含恢复段，因此上述模型时间合计与顺序链路时间为下界，不能用于精确速度排名。

复核未完成批次原因计数：{'budget_exhausted': 25, 'validation_rejected': 12, 'context_budget': 1, 'timeout': 1, 'provider_error': 2}。非完成阶段错误详见本地 `report-data.json`。

## 全部项目逐项结果

TP/FP 为官方匹配后的计数；多 CWE 告警按作者 parser 方式展开。

| 项目 | CodeQL TP/FP | 综合支持 TP/FP | 保留未决 TP/FP | 粗筛窗口 已检查/可选 | 未决 | 状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| realvuln-damn-vulnerable-flask-application | 3/7 | 7/8 | 9/14 | 5/10 | 8 | partial |
| realvuln-damn-vulnerable-graphql-application | 0/3 | 1/1 | 1/2 | 5/91 | 1 | partial |
| realvuln-djangoat | 12/38 | 2/2 | 13/38 | 5/181 | 25 | partial |
| realvuln-dsvpwa | 3/12 | 3/1 | 3/3 | 2/21 | 1 | partial |
| realvuln-dsvw | 10/20 | 4/0 | 10/16 | 2/5 | 10 | partial |
| realvuln-dvblab | 8/10 | 7/4 | 11/6 | 1/13 | 4 | partial |
| realvuln-dvpwa | 1/2 | 4/1 | 5/3 | 8/29 | 3 | partial |
| realvuln-extremely-vulnerable-flask-app | 4/2 | 6/3 | 7/4 | 4/38 | 2 | partial |
| realvuln-flask-xss | 1/3 | 1/1 | 2/1 | 6/30 | 1 | partial |
| realvuln-insecure-web | 4/5 | 6/5 | 7/7 | 3/3 | 3 | partial |
| realvuln-intentionally-vulnerable-python-application | 3/4 | 6/1 | 7/9 | 1/1 | 7 | partial |
| realvuln-lets-be-bad-guys | 4/8 | 0/0 | 4/8 | 0/42 | 4 | partial |
| realvuln-owasp-web-playground | 2/11 | 2/2 | 2/2 | 0/54 | 0 | partial |
| realvuln-pygoat | 16/58 | 2/6 | 16/57 | 5/240 | 27 | partial |
| realvuln-python-app | 5/15 | 7/4 | 7/6 | 4/52 | 2 | partial |
| realvuln-python-insecure-app | 0/1 | 3/1 | 3/2 | 6/6 | 1 | partial |
| realvuln-pythonssti | 0/1 | 1/1 | 1/1 | 1/1 | 0 | completed |
| realvuln-threatbyte | 3/24 | 1/2 | 6/26 | 7/30 | 15 | partial |
| realvuln-vampi | 1/8 | 2/2 | 3/6 | 7/31 | 5 | partial |
| realvuln-vfapi | 1/5 | 6/2 | 6/2 | 5/8 | 0 | partial |
| realvuln-vulnerable-api | 0/0 | 3/0 | 3/0 | 7/12 | 0 | partial |
| realvuln-vulnerable-flask-app | 3/6 | 7/0 | 7/4 | 4/13 | 3 | partial |
| realvuln-vulnerable-python-apps | 2/11 | 2/2 | 5/11 | 7/28 | 12 | partial |
| realvuln-vulnerable-tornado-app | 4/9 | 6/4 | 8/5 | 4/13 | 3 | partial |
| realvuln-vulnpy | 6/6 | 6/0 | 6/0 | 6/130 | 0 | partial |
| realvuln-vulpy | 10/28 | 6/2 | 13/24 | 7/86 | 13 | partial |

## 版本、边界和复现

- 日志复查修正了评测适配器的模型 CWE 前导零规范化（CWE-079 → CWE-79）；未新增模型调用。原评分保存在 attempts/02-pre-cwe-normalization/。综合支持 TP 从 100 修正为 101，FP 从 56 修正为 55。
- CodeQL 2.23.5，Python 查询包 codeql/python-queries@1.6.0，标准 code-scanning 套件。
- 模型 `deepseek-v4.1-flash`，Scout v7 / Review v12；每阶段默认调用、token、时间预算 24 / 100000 / 300 秒。
- 标注来源官方 GitHub 历史 `55350cdc0f0f7db85d1f0b97649df07e6d63c665`；全部目标 commit 与官方 v1.0 清单一致。HF 无法连接，未验证 HF 字节身份。后来的 GitHub v1.0 标注增至 697，本轮未混入新增标签。
- 模型使用独立源码目录，evaluator-only 标签、描述、PoC 和作者结果没有进入模型输入或 RAG。目标仓库原有文档/注释保留，Flask 曾用于开发校准，不能称整个数据集独立盲测。
- 这是生产适配器、服务、LangGraph、数据库和真实模型的核心链路评测；研究注册桥绕过 ZIP 上传/GUI。OWASP Web Playground 3066 文件超过当前上传文件数限制。未评估修复与新规则生成。
- 冻结代码未做基于本轮结果的产品改造。源码/实现哈希、阶段 ID、实际响应、SARIF、失败历史保存在本地忽略目录。首次查询包路径错误记录保留，路径修正后复用数据库；报告计正常抽取与查询成本，不隐藏这次环境错误。
- 评分用官方文件/CWE/±10 行 matcher，每条 GT 只消耗一次；重复告警计额外 FP。未知 CWE 保留为未匹配 FP。标签可能不完备，未匹配 FP 不等于已用利用测试证明安全。

详细协议：[realvuln-20261013-protocol.md](../experiments/realvuln-20261013-protocol.md)。

原始与机器结果目录：`artifacts/research/realvuln/20261013-paper-v1/`；主汇总 `scores/summary.json`，逐项匹配 `scores/<project>/`，配对 gains/losses、错误与预算 `report-data.json`。

从仓库根目录重评分（不会新增模型调用）：

```sh
PYTHONPATH=system system/.venv/bin/python -m scripts.benchmarks.realvuln_score \
  --output artifacts/research/realvuln/20261013-paper-v1
PYTHONPATH=system system/.venv/bin/python -m scripts.benchmarks.realvuln_report \
  --output artifacts/research/realvuln/20261013-paper-v1 \
  --report benchmarks/reports/realvuln-20261013-results.md
```
