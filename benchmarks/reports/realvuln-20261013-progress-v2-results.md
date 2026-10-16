# RealVuln 论文全 26 项目：单 CodeQL 与综合审计系统

日期：2026-10-13。全部项目已尝试；默认预算下的部分覆盖和未决结果单独保留。

综合系统相对单 CodeQL：TP +127，FP -73，Recall +18.79 个百分点，Precision +24.68 个百分点，F3 +19.28。此结果仅代表本轮冻结实现、模型和预算。

## 两条链路的主结果

分母为论文全部 676 条漏洞；另有 120 条 FP traps。使用官方 strict micro 评分。

| 链路 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 单 CodeQL | 106 | 297 | 570 | 26.30% | 15.68% | 19.65 | 16.34 |
| 综合系统：AI 支持输出 | 233 | 224 | 443 | 50.98% | 34.47% | 41.13 | 35.62 |

综合系统主结果取 Review v12 的 `supported`，是经过产品结构/证据门的 AI 分类，不是本次新增的独立人工确认。未决、证据不足和未检查候选仍保留在产物中，未默认判为误报。

| 辅助口径 | TP | FP | FN | Precision | Recall | F1 /100 | F3 /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 综合系统：保留所有未决，仅排除已验证误报 | 388 | 674 | 288 | 36.53% | 57.40% | 44.65 | 54.30 |
| 复核前 CodeQL＋粗筛原始并集 | 390 | 858 | 286 | 31.25% | 57.69% | 40.54 | 53.19 |

按黄金标签 ID 配对，最终支持输出新增命中 166 条、失去基线命中 39 条；失去支持可能来自明确排除、证据不足或尚未复核，需要结合每项目记录分析，不能一概称成功过滤。

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

- CodeQL 成功 26/26；综合阶段结果状态：{'partial': 22, 'completed': 4}。
- Scout/Review 阶段状态：{'completed': 52}；覆盖状态与阶段状态分别记录。未决候选 522 个。
- 独立粗筛检查 955/1168 个非第三方可选窗口；停止原因：{None: 23, 'timeout': 2, 'provider_error': 1}。不能称为所有文件/业务流程均检查完毕。
- 实际模型调用 2189 次，输入 19396271 tokens，输出 2296333 tokens。服务未提供可靠统一单价，本报告不虚构美元成本。
- CodeQL 抽取＋查询时间合计 750.9 秒；模型阶段合计 17435.2 秒。
- 每项目顺序链路中位数 633.1 秒；项目并发 2，static 输出共享，以上不是产品双引擎并发端到端延迟。本轮模型阶段墙钟时间按各阶段完整运行记录统计。

复核未完成批次原因计数：{'validation_rejected': 68, 'verification_failed': 1, 'schema_invalid': 5, 'audit_error': 1, 'context_budget': 2, 'provider_error': 2, 'timeout': 2}。非完成阶段错误详见本地 `report-data.json`。

## 全部项目逐项结果

TP/FP 为官方匹配后的计数；多 CWE 告警按作者 parser 方式展开。

| 项目 | CodeQL TP/FP | 综合支持 TP/FP | 保留未决 TP/FP | 粗筛窗口 已检查/可选 | 未决 | 状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| realvuln-damn-vulnerable-flask-application | 3/7 | 8/8 | 8/12 | 10/10 | 4 | partial |
| realvuln-damn-vulnerable-graphql-application | 0/3 | 10/8 | 19/24 | 91/91 | 25 | partial |
| realvuln-djangoat | 12/38 | 25/46 | 29/72 | 177/181 | 30 | partial |
| realvuln-dsvpwa | 3/12 | 20/13 | 23/24 | 21/21 | 14 | partial |
| realvuln-dsvw | 10/20 | 13/3 | 14/5 | 4/5 | 2 | partial |
| realvuln-dvblab | 8/10 | 16/16 | 16/17 | 12/13 | 1 | partial |
| realvuln-dvpwa | 1/2 | 11/11 | 11/14 | 28/29 | 3 | partial |
| realvuln-extremely-vulnerable-flask-app | 4/2 | 15/15 | 16/18 | 38/38 | 4 | partial |
| realvuln-flask-xss | 1/3 | 13/12 | 17/22 | 30/30 | 14 | partial |
| realvuln-insecure-web | 4/5 | 7/5 | 8/6 | 3/3 | 2 | completed |
| realvuln-intentionally-vulnerable-python-application | 3/4 | 6/2 | 6/2 | 1/1 | 0 | completed |
| realvuln-lets-be-bad-guys | 4/8 | 13/9 | 15/11 | 42/42 | 4 | partial |
| realvuln-owasp-web-playground | 2/11 | 8/4 | 16/34 | 54/54 | 38 | partial |
| realvuln-pygoat | 16/58 | 0/0 | 29/145 | 62/240 | 131 | partial |
| realvuln-python-app | 5/15 | 0/0 | 13/44 | 33/52 | 44 | partial |
| realvuln-python-insecure-app | 0/1 | 1/0 | 1/0 | 0/6 | 0 | partial |
| realvuln-pythonssti | 0/1 | 2/1 | 2/1 | 1/1 | 0 | completed |
| realvuln-threatbyte | 3/24 | 12/16 | 17/36 | 30/30 | 21 | partial |
| realvuln-vampi | 1/8 | 6/8 | 10/22 | 31/31 | 16 | partial |
| realvuln-vfapi | 1/5 | 5/2 | 5/2 | 8/8 | 0 | partial |
| realvuln-vulnerable-api | 0/0 | 8/0 | 9/2 | 12/12 | 3 | completed |
| realvuln-vulnerable-flask-app | 3/6 | 9/10 | 10/13 | 13/13 | 4 | partial |
| realvuln-vulnerable-python-apps | 2/11 | 10/9 | 16/15 | 28/28 | 12 | partial |
| realvuln-vulnerable-tornado-app | 4/9 | 7/10 | 7/12 | 13/13 | 2 | partial |
| realvuln-vulnpy | 6/6 | 4/11 | 33/32 | 127/130 | 46 | partial |
| realvuln-vulpy | 10/28 | 4/5 | 38/89 | 86/86 | 102 | partial |

## 版本、边界和复现

- 评分统一规范化 CWE 前导零；源码、标注与模型产物分离。
- CodeQL 2.23.5，Python 查询包 codeql/python-queries@1.6.0，标准 code-scanning 套件。
- 模型 `deepseek-v4.1-flash`，Scout v7 / Review v12；执行模式 progress；调用、token、时间预算（0 表示无阶段总上限） 0 / 0 / 0 秒。
- 标注来源官方 GitHub 历史 `55350cdc0f0f7db85d1f0b97649df07e6d63c665`；全部目标 commit 与官方 v1.0 清单一致。HF 无法连接，未验证 HF 字节身份。后来的 GitHub v1.0 标注增至 697，本轮未混入新增标签。
- 模型使用独立源码目录，evaluator-only 标签、描述、PoC 和作者结果没有进入模型输入或 RAG。目标仓库原有文档/注释保留，Flask 曾用于开发校准，不能称整个数据集独立盲测。
- 这是生产适配器、服务、LangGraph、数据库和真实模型的核心链路评测；研究注册桥绕过 ZIP 上传/GUI。OWASP Web Playground 3066 文件超过当前上传文件数限制。未评估修复与新规则生成。
- 执行期间冻结实现保持不变。源码/实现哈希、阶段 ID、实际响应、SARIF、失败历史保存在本地忽略目录。
- 评分用官方文件/CWE/±10 行 matcher，每条 GT 只消耗一次；重复告警计额外 FP。未知 CWE 保留为未匹配 FP。标签可能不完备，未匹配 FP 不等于已用利用测试证明安全。

详细协议：[realvuln-20261013-progress-v2-protocol.md](../experiments/realvuln-20261013-progress-v2-protocol.md)。

原始与机器结果目录：`artifacts/research/realvuln/20261013-progress-v2/`；主汇总 `scores/summary.json`，逐项匹配 `scores/<project>/`，配对 gains/losses、错误与预算 `report-data.json`。

从仓库根目录重评分（不会新增模型调用）：

```sh
PYTHONPATH=system system/.venv/bin/python -m scripts.benchmarks.realvuln_score \
  --output artifacts/research/realvuln/20261013-progress-v2
PYTHONPATH=system system/.venv/bin/python -m scripts.benchmarks.realvuln_report \
  --output artifacts/research/realvuln/20261013-progress-v2 \
  --report benchmarks/reports/realvuln-20261013-progress-v2-results.md
```
