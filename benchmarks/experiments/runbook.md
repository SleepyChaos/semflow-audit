# 实验执行与断点恢复规程

2026-10-05。用于跨长上下文、模型切换和进程中断的连续工作。当前是入口规范，统一 runner 在 E03 实现；下文文件契约不是已存在的新测试产物。

## 1. 本地目录与输入隔离

```text
benchmark-data/experiments/              # 本计划、状态、决策日志
benchmark-data/evaluator-only/experiments/<experiment_id>/
  tasks.json                            # 冻结任务、组分配、根因与答案
  relevance.json                        # 知识/范例相关性与复核状态
  oracles/                              # 隐藏安全/业务测试
benchmark-data/model-inputs/<input_id>/  # 白名单输入、去标签源码
artifacts/research/formal/<experiment_id>/
  config.json                           # 不含密钥；身份与预算
  input-receipts.json                   # 版本、转换差异和摘要
  results.jsonl                         # 每任务/组/轮/尝试不可变结果
  runs/<run_id>/<attempt_id>/            # 输出、SARIF、规则、diff、测试与时序
  summary.json                          # 从完整结果生成，不手改分数
```

后三类本地数据已有 gitignore 规则，不发布答案、第三方整仓和实际审计产物。相对路径从仓库根目录解析。

- 发现阶段不得加载任务答案或漏洞描述；模型工具根目录限定为当次 `model-inputs` 副本。
- 规则/修复只增加协议明确允许的字段；不直接序列化 PatchEval 整项数据。
- 生成器、工具工作区、检索语料均不可包含隐藏 gold。评测器评分只返回结果到汇总，不回传隐藏内容给生成循环。
- API 地址可登记，Authorization、key、带凭据 URL 和 `.env` 内容不得写入输入/日志。记录 provider 身份，不复制秘密。

## 2. 任务、运行与尝试的身份

- `experiment_id`：计划版本+配置摘要；配置、语料或评分变化生成新身份。
- `task_id`：稳定匿名 ID；`group_id` 绑定仓库、漏洞别名和根因，用于拆分与统计。
- `run_id`：实验+任务+对照组+重复编号；`attempt_id`：一次初始执行或明确记录的重跑。
- 原始第一次尝试保留；模型内部允许的修订属于该 run，不可当成新增任务。
- 原始结果以创建后不可变文件保存，后续评分更正另存评分版本与理由。
- `state.json` 是工作任务状态；`results.jsonl` 是实验运行结果，两者不可混用。

每条运行记录最低字段：任务/组/轮/尝试身份、配置/源码/语料摘要、起止时间与墙钟、各阶段耗时、请求/token、预算用量、模型响应身份、执行状态、评分状态、产物引用、失败/未决原因。

执行状态：`succeeded` / `failed` / `timeout` / `cancelled` / `unsupported` / `interrupted`。
评分状态独立：`confirmed` / `rejected` / `unresolved` / `unknown` / `infra_failure`。运行成功不自动代表漏洞确认、QL 有效或修复正确。

修复 verified 必须额外具备 `security_oracle=passed`、`functional_oracle=passed` 及校准身份。扫描正常空结果与扫描失败必须区分。

## 3. 一次工作会话怎么推进

1. 读取 `state.json` 的 `next_action`，检查该任务的依赖与门槛。
2. 查最近日志和已有产物，确认是否已有同一 run；不要直接再次付费调用模型。
3. 开始时把工作任务标记 `in_progress`，登记当前批次、预计运行数与固定上限。
4. 先做最小协议/开发 smoke；正式隐藏任务只在 G2 后执行。
5. 每个运行结束先落盘原始产物与收据，再更新索引。批次结束再生成汇总。
6. 工作任务满足 acceptance 并验证产物后才能标 `complete`；若只完成部分，用 `in_progress` 并写剩余项。
7. 结束会话前更新状态、时间、证据路径、剩余预算、`next_action` 和日志，明确下一条安全操作。

不要为了赶进度执行互有依赖的任务。独立的本地读/校验可批量，源码和评分器更改后必须重新核对对应身份。

## 4. 中断与恢复

- 优先核对落盘文件、hash、外部进程和阶段 ID。已有完整输出的 run 直接评分/汇总，不重复生成。
- 外部请求已发出但返回未保存，标记 `interrupted`，说明请求和计费状态不确定；重跑创建新 attempt，保留未知原始耗时/成本，不能装作从未发生。
- 输入不变但基础设施恢复可重跑；默认最多一次基础设施重跑。仍失败记为 infra-failure，后续追加批次需写理由。
- 改 prompt、修订规则预算或用隐藏失败来改实现，属于新实验版本；旧分母、旧原始结果保留。
- 发现泄漏时隔离受影响组，登记泄漏来源；不能仅移除输掉的任务或把“模型已经看过”仍称完全隐藏。
- 找不到合格 oracle 时写 `deferred` 和原因，仅暂缓依赖它的任务，继续其他可执行主线。

## 5. 旧脚本如何复用

| 旧脚本 | 可复用部分 | 必须改造的评测假设 |
| --- | --- | --- |
| `real_pair_baseline.py` | CodeQL 数据库、SARIF、快照与计时 | 写死扩展 suite；位置命中不等于根因正确；要用冻结任务清单 |
| `dual_discovery_comparison.py` | 真实服务/阶段调用、候选与复审产物 | 6 个开发微样例；文件+CWE 匹配不够；需完整项目覆盖与四组对照 |
| `semantic_comparison.py` | 独立候选副本、语义流程调用、测试隔离 | 原微样例和语法检查不够；区分固定漏洞修复与端到端发现修复 |
| `rule_holdout.py` | 编译/执行、正负例结果读取 | 原规则是人工种子且局部行号评分，不是正式 RAG 生成实验 |
| `inventory_collected_materials.py` | 材料格式/哈希核对 | 材料完整性不代表任务可运行；不要用它替代 oracle 校准 |

E03 优先薄 runner + 任务契约 + 各链路适配器，避免一份长脚本包办下载、生成、评分和报告。需要测试的是泄漏隔离、失败状态、恢复去重、评分根因、隐藏反馈阻断；文档调整无需重跑全系统。

## 6. 首个执行动作

从 E00 开始：生成当前工作树/流程/提示摘要，核实 suite 和 CLI/pack，读取不含秘密的模型与索引身份，然后整理旧实验/RAG 暴露清单。

现阶段没有统一正式 runner 命令；E03 实现后把准确命令、前提和预期产物追加在这里，禁止杜撰“现在可以直接运行”的命令。
