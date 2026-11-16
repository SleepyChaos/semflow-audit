# BenchmarkPython 改进收束与合并记录

`BP-CHECKPOINT-20261110 | 2026-11-10T13:55:00+08:00 | completed`

本记录归档当前进度，按用户指令停止新增实验。completed 仅表示检查点归档完成；研究 TODO 未全部完成。

## 合并范围与依据

已验证的发现覆盖组合以 `c5ea14b` 为集成截点，效果实现为 `f6dc761`。包含密码学随机/哈希任务拆分、API 导航锚点、相邻 CWE 提示、多标签证据过滤与 sidecar、独立发现候选评分，以及冻结/监督/验收流水线和必要的历史机制实验驱动。保留 Git 祖先关系，便于从实验源码追溯至 main。

锚点只提供导航，不直接生成漏洞结论；无效附加标签不得吞掉已通过原证据门的主候选。新标签仍须证据。多标签组合与锚点开关接在 `system/scripts/benchmarks/mechanisms/discovery.py` 的实验计划中；本次源码合并不意味着产品 API 已默认启用完整多标签或反馈续搜，也不修改服务器部署。

服务器既有汇总经重新读取，完成标记和监督器均确认 clean completion。两次覆盖实验各自 identity.json 的 429 个源码文件哈希与对应 Git 提交逐项一致，0 项不匹配。

| 固定样本 | legacy TP / FP | 锚点+多标签组合 TP / FP | Recall | FPR | 保守计费 token 比率 |
|---|---:|---:|---|---|---:|
| 40 例，20 正/20 负，28 组 | 12 / 3 | 17 / 1 | 60% → 85% | 15% → 5% | 0.937 |
| 历史 120 例，60 正/60 负，37 组 | 48 / 29 | 57 / 14 | 80% → 95% | 48.33% → 23.33% | 0.924 |

上表为静态+发现联合候选口径。120 例的纯 Discovery 口径为 legacy 47 TP/29 FP，组合 57 TP/12 FP；两种口径不混用。40 例两种口径的 TP/FP 相同。成本为 charged tokens，含未知用量的保守预留，不等同于接口实际账单金额。

限制：120 例包含前述全部 40 例，只有 80 例新增，不能算独立留出验证；结果受开发集暴露、单次模型随机性及聚焦源码/运行时配置影响。锚点单项未稳定提升 weakrand，不能把组合收益归因于每个组件。机制族 55/60 与精确 CWE 57/60 的不一致仍待诊断；不以该三层指标支撑已完成结论。这里也不是全量 1230 例的改进后成绩。

## 保留在研究分支的改动

- 分支：`codex/owasp-feedback-small-20261110`，开发检查点 `9f28785`；完整历史另存本地 Git bundle。
- 候选复审：`d4dced3` 的 143 个候选，57 个目标正例候选中 B1 supported 55，B2 supported 54；缺逐 CWE、legacy 池对照、负例误报和完整成本验收，不作为已证明有效机制集成。
- 反馈协议、共享证据日志、有界 A3 continuation、六例启动器：15 项离线契约测试通过，真实模型实验未启动。不能声称新增 TP、双 Agent 交互有效或闭环已完成。
- 仍需处理全局预算核算、未复审新增候选显式 unknown、逐标签验收和 C1–C4 消融。详见 [反馈开发检查点](feedback-small-checkpoint-20261110.md)。

未验收的复审保留和新反馈开发代码不随 `c5ea14b` 进入 main。main 中已有的历史 C 反馈脚本仅用于原始基线重现，不代表上述新交互闭环。

## TODO 当前进度

| 状态 | 项目 |
|---|---|
| completed | BP-COV-001 |
| in_progress | BP-COV-002、003、004、005；BP-FB-001、002、003、004、005 |
| planned | BP-FB-006、007 |

共 12 项研究目标，1 项完成、9 项进行中、2 项待开展。源码具备阶段性合并依据不等于研究目标全部完成。主入口：[TODO](benchmarkpython-improvement-todo-20261109.md)、[改进树](benchmarkpython-improvement-tree-20261110.md)。

后续只运行小样本可行性测试，执行固定测试+验收程序后查看结果，必要时查日志；不自动扩大中等或全量。本次收束不继续开发或新增模型调用。

## 产物与源码位置

服务器根目录：`/home/work/zdk/experiments/benchmarkpython-mechanisms-20261103/`。

- `epoch-20261110-coverage-cwe-min40-f6dc761/`：40 例 summary、acceptance、completed、case-results、identity 及原始调用历史。
- `epoch-20261110-coverage-medium120-c5ea14b/`：历史 120 例同类文件；不重跑。
- `epoch-20261110-retention-medium120-d4dced3/`：143 候选 summary、completed；无 acceptance.json，不能据 clean completion 宣称效果通过。
- 原始首轮 `epoch-20261104-083256/` 和 420 例回归 `epoch-20261106-coverage-full-420-v3-16df9a8/` 保持原样；重复 2/3 不启动。

本地下载：仓库工作区的 `output/benchmarkpython-checkpoint-20261110/`，包含现有三次实验摘要/CSV/身份、监督器快照、此前失败的小样本摘要、测试日志、SHA256 清单及反馈开发 bundle。它是本地归档，不加入 Git。原始完整响应、全部物理尝试和未知用量仍以服务器各 epoch 账本为准，本次未复制为新的实验成绩。

Git 仅保存源码、测试、计划、人工解读和 [哈希索引](benchmarkpython-checkpoint-index-20261110.json)，不提交密钥、原始审计产物或上传项目。既有失败结果和更正记录均保留。

## main 集成验收

集成基于同步后的 `origin/main`（`52d8fa2`），在隔离工作树进行，原工作区未切分支、不批量暂存。

集成回归发现旧 V4/V5 的 8 项 task_checks 契约与新增 10 项任务不兼容；修复为仅语义 V6+ 计划分配专用密码学任务，旧版本保留原任务集合。没有放宽证据门，也没有将未检查项改成成功。本次不会为兼容修复重新调用模型或改写旧实验 identity。

最终集成验证：149 项测试通过，另有 10 项子测试通过；新增兼容修复的 Ruff 检查通过。使用仅绑定本机的临时 pgvector 数据库和假模型，不访问部署、不新增付费调用。测试日志保存在本地 `coverage-main-integration-final-20261110.log`。合并记录由 Git 保留，暂未推送远端。
