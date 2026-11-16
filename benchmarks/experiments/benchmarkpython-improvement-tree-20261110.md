# BenchmarkPython 改进树与分叉验证记录

## 当前阶段分支：Agent 协作 → CodeQL 能力聚焦

更新时间：2026-11-16T15:48:54+08:00。主 TODO 顶部 AGC 表是任务状态的权威入口；下方旧树的“当前”仅指历史记录时点。

| 节点 ID | 北京时间 | 状态 | 改进归属 | 模块/部位 | 任务映射 | 进入条件／失败回退 |
| --- | --- | --- | --- | --- | --- | --- |
| AGC-TREE-PRE | 2026-11-16T15:48:54+08:00 | planned | 实验内核核对＋独立评测 | discovery 基线；样本/预算协议 | PRE-001～003 | 前置清单冻结；失败留在本节点 |
| AGC-TREE-LOOP | 2026-11-16T15:48:54+08:00 | planned | 共享契约＋实验内核 | contracts；discovery 单 Agent 循环 | CON-001、CORE-001 | PRE 完成；失败回 PRE/LOOP |
| AGC-TREE-COOP | 2026-11-16T15:48:54+08:00 | planned | 实验内核＋实验 CLI | discovery 角色交接/编排；CLI 装配 | CORE-002～004、CLI-001 | LOOP 定向验收通过；失败回 LOOP/COOP |
| AGC-TREE-PILOT | 2026-11-16T15:48:54+08:00 | planned | 独立评测 | 技术门与六任务机制对照 | TEST-001、EXP-001、GATE-001 | G1 后才跑真实小样本；G2 失败回 COOP |
| AGC-TREE-SCOPE | 2026-11-16T15:48:54+08:00 | planned | 独立评测／研究选题 | CodeQL 能力缺口与约两类漏洞 | SCOPE-001/002 | G2 通过才进入；无共同缺口则留在本节点重审选题 |

任务简写均以 AGC- 开头。每次尝试登记独立 attempt ID、北京时间、冻结源码/方法/Prompt、epoch、输入与预算摘要、技术结论、效果结论及回退节点；尚无本阶段运行，不预造尝试或成绩。只做固定小样本，不自动进入下方历史中等/全量路径。

---

## 历史原文：2026-11-10 改进树

更新时间：2026-11-10T13:55:00+08:00
主 TODO：[benchmarkpython-improvement-todo-20261109.md](benchmarkpython-improvement-todo-20261109.md)
范围：只记录 BenchmarkPython 改进分叉、最小验证、中等抽检和回退关系；不替代主 TODO，也不覆盖历史结果。

## 使用规则

每个节点都记录稳定 ID、北京时间时间戳和状态。节点可以重复出现，但每次重复必须使用新的尝试 ID、冻结代码和 epoch。节点完成一次改造后按以下顺序推进：

当前执行规则（2026-11-10 用户指令）：只做固定小样本可行性验证，通过固定测试+验收流水线再决定分支；下述中等抽检流程仅保留为历史设计，不自动执行。当前已按用户要求收束改动。

1. **最小验证**：固定小样本、固定输入和预算，验证结构、账本、失败保留和目标指标方向。
2. **中等抽检**：最小验证有效后，扩大到预先固定的中等样本，验证收益是否跨类别、跨项目或跨分组保持。
3. **分支推进**：两级验证都有效才进入子节点；任一级失败则保留产物，回退到上游节点选择其他分支。

“技术通过”只表示代码、schema、账本或监督器符合契约；“效果通过”必须满足节点的指标门槛。未达到效果门槛不得合并主分支或启动全量测试。

## 当前树

```text
BP-TREE-ROOT-20261110 [in_progress]
├─ BP-TREE-COV-001 任务拆分与类别基线 [completed]
├─ BP-TREE-COV-002 候选/CWE 对齐诊断 [in_progress]
│  ├─ COV-002-A 源窗口与 API 锚点调度
│  ├─ COV-002-B 候选位置、机制族、CWE 配对
│  ├─ COV-002-C 精确 CWE 提示与示例约束
│  └─ COV-002-D 静态告警到 CWE 的证据化交叉映射
├─ BP-TREE-COV-003 复审候选保留 [in_progress, depends=COV-002]
│  ├─ COV-003-A 位置命中与机制族候选双视图
│  ├─ COV-003-B B1/B2 多标签保留对照
│  ├─ COV-003-C unknown/insufficient 保留门
│  └─ COV-003-D lineage 去重与候选合并
├─ BP-TREE-FB-001 B2→A3 结构化反馈 [in_progress, depends=COV-003]
│  ├─ FB-001-A 缺 CWE 反馈
│  ├─ FB-001-B 缺证据/调用链反馈
│  ├─ FB-001-C A3 bounded continuation
│  └─ FB-001-D 反馈新增候选门控
├─ BP-TREE-FB-002 共享证据与闭环控制 [planned, depends=FB-001]
│  ├─ FB-002-A 不可变 evidence event
│  ├─ FB-002-B 轮次/无进展停止
│  ├─ FB-002-C 物理尝试与未知成本账本
│  └─ FB-002-D C1-C4 配对消融
└─ BP-TREE-PAPER-001 论文级配对分析 [planned, depends=FB-002]
   ├─ PAPER-A 项目/案例配对与 bootstrap
   ├─ PAPER-B Recall/FPR/F1/F3 分层
   ├─ PAPER-C 新增 TP/FP lineage 追踪
   └─ PAPER-D 成本和变量控制声明
```

## 节点记录

### BP-TREE-ROOT-20261110 | 2026-11-10T10:30:00+08:00 | in_progress

目标：以“候选覆盖→复审保留→反馈闭环→论文配对”的顺序推进，不把多个机制的收益混成一个双 Agent 结论。

当前入口：`BP-TREE-COV-002`。原因是三次 40 例三臂验证中，锚点和多标签没有提升精确 CWE 覆盖；位置命中提高或保持，但目标 CWE 仍然丢失。

回退规则：任何子节点的中等抽检失败，回到最近一个通过的上游节点；不得沿失败分支继续扩大样本。

### BP-TREE-COV-001 | 2026-11-10T10:30:00+08:00 | completed

内容：拆分 `cryptographic_randomness` 与 `cryptographic_hashing`，建立类别基线和分层指标。

最小验证：类别任务、样本标签隔离、三层指标契约测试。
中等抽检：420 例覆盖诊断，保留位置/机制族/精确 CWE 和 B2 正例损失。
结果：技术和诊断均通过；弱随机数仍是主要召回短板。
证据：`epoch-20261106-coverage-full-420-v3-16df9a8` 及本地 `coverage-420-layered/`。

后续方向：不再重复本节点；进入候选/CWE 对齐诊断。

### BP-TREE-COV-002 | 2026-11-10T10:30:00+08:00 | in_progress

目标：解释“位置/机制族命中但精确 CWE 不命中”，先修复候选语义链再测复审。

候选分支：

- **COV-002-A：源窗口与 API 锚点调度**。确认锚点覆盖目标操作、跨文件调用链和安全用途；失败回到本节点改窗口/调度。
- **COV-002-B：候选位置、机制族、CWE 配对**。逐条检查 `location`、`mechanism_family`、`primary_weakness`、`weaknesses[]` 和 claim evidence 是否指向同一操作；优先级最高。
- **COV-002-C：精确 CWE 提示与示例约束**。要求模型先说明候选操作，再给 CWE claim；不把 API 名称直接当漏洞。
- **COV-002-D：静态告警交叉映射**。将 CodeQL tags 作为导航和候选属性输入，保留多 CWE 证据，不把 evaluator 标签放进模型上下文。

已尝试分支：

- **尝试 `35720e9` | 2026-11-09T20:00:00+08:00 | failed_effect**：三臂 40 例完成；多标签 schema 过严，`anchors_multilabel` 精确 CWE 7/20，出现 7 次 schema_invalid。
- **尝试 `8a070e5` | 2026-11-09T20:00:00+08:00 | technical_pass_effect_failed**：逐条过滤无效 claim、保留主候选；schema_invalid 基本消除，精确 CWE 10/20，仍低于 legacy 12/20。
- **尝试 `565b2ac` | 2026-11-09T20:00:00+08:00 | effect_failed**：增加锚点使用 prompt；锚点确实进入 29 个多标签上下文，精确 CWE 9/20，legacy 为 11/20，仍未达门槛。

最小验证结果：三次均 clean completion；第三次技术链通过。
中等抽检：未执行。原因：最小验证的精确 CWE 增益门槛未通过。
当前结论：不能进入 COV-003，先从 COV-002-B 或 COV-002-A 继续。

效果门槛：相对同 epoch legacy，正例精确 CWE 候选覆盖提升至少 5 个百分点；位置覆盖下降不超过 5 个百分点；FPR 增幅不超过 5 个百分点；无 evaluator label 泄漏；unknown 和失败成本完整。

### BP-TREE-COV-003 | 2026-11-10T12:47:40+08:00 | in_progress

依赖：COV-002 最小验证和中等抽检通过。
目标：验证复审是否吞掉新增机制族/多 CWE 候选。

候选分支：

- **COV-003-A：双视图复审**。同时给 B1/B2 位置候选和精确 CWE 候选，分别记录保留率。
- **COV-003-B：B1/B2 多标签对照**。固定候选池，只比较普通复审和结构化复审对附加 CWE 的 supported/excluded/unknown 转移。
- **COV-003-C：unknown/insufficient 保留门**。证据不足时保留未决，不把候选静默删除。
- **COV-003-D：lineage 去重与候选合并**。同一位置不同机制、同一机制不同 CWE 分开记录，禁止覆盖原候选。

最小验证：固定 20–40 个候选，逐条回放复审输入、输出、证据和 lineage。
中等抽检：固定 100–160 个候选，覆盖 weakrand、hash 和至少两类控制类别。
进入下一节点条件：新增目标机制候选保留率不低于 legacy 候选保留率，且新增 TP > 0；schema_invalid、FP、unknown 分开统计。

实际结果：中等抽检使用 143 个 anchors+multilabel 候选，B1 保留目标正例候选 55/57，B2 保留 54/57；B1/B2 的所有候选 verdict 均有记录，B2 的 unknown/insufficient 更多。首次汇总因 source candidate ID 与 review candidate ID 未通过 lineage 映射而全部显示 unknown，修复 `d4dced3` 后重跑通过。

证据：服务器 epoch `epoch-20261110-retention-medium120-d4dced3`，supervisor `clean_completion`。该节点满足候选保留率和可回放门槛，进入 FB-001。

### BP-TREE-FB-001 | 2026-11-10T10:59:09+08:00 | in_progress

依赖：COV-003 通过。
目标：让 B2 的结构化反馈真正回到 A3，形成有界 continuation。

候选分支：

- **FB-001-A：缺 CWE 反馈**。反馈目标机制族、候选操作和待确认 CWE，不提供 evaluator 真值。
- **FB-001-B：缺证据/调用链反馈**。只请求缺失源码页、调用者或绑定事实。
- **FB-001-C：A3 bounded continuation**。在原 snapshot 和剩余预算内执行一次定向搜索。
- **FB-001-D：反馈新增候选门控**。新增候选必须有父候选/属性、位置、独立证据和 `origin=feedback`。

最小验证：离线 schema、越界路径、未知 candidate、重复请求、无证据请求和预算为零。
中等抽检：20–40 个反馈任务，至少覆盖缺 CWE、缺调用链和缺证据三类。
进入下一节点条件：反馈任务 100% 可回放，新增候选 lineage 完整，重复请求不增加物理调用。

当前实现：`c1b61cd` 增加 `FeedbackRequest`、请求 hash、不可变 receipt 和 candidate/file/evidence/budget/duplicate 门控；`f2eddb3` 增加 continuation candidate 的 parent/snapshot/path/evidence lineage 门控；7 项离线测试通过。`6ec5665` 增加 30 个固定候选的协议回放，30/30 请求唯一且无模型调用。

当前状态：协议最小验证和中等协议抽检已通过，真实 B2→A3 feedback continuation 尚未运行。下一步从 FB-001-A/B 中选一个固定 20–40 任务样本做最小真实验证。

### BP-TREE-FB-002 | 2026-11-10T10:30:00+08:00 | planned

依赖：FB-001 通过。
目标：建立共享证据事件和闭环停止控制。

候选分支：

- **FB-002-A：不可变 evidence event**。A3/B2 共享同一 evidence ID、snapshot hash 和源码内容。
- **FB-002-B：轮次/无进展停止**。限制 continuation 轮次，重复反馈或无新增证据自动停止。
- **FB-002-C：成本账本**。分开记录逻辑请求、物理尝试、未知用量、schema_invalid 和新增候选成本。
- **FB-002-D：C1-C4 配对消融**。无反馈、单向反馈、共享证据和完整闭环分别建 epoch。

最小验证：故障注入和离线回放。
中等抽检：同一 40–80 例样本，固定四个反馈配置。
进入下一节点条件：闭环新增 TP 可追溯，新增 FP 不超过 5 个百分点，成本增量有账本解释。

### BP-TREE-PAPER-001 | 2026-11-10T10:30:00+08:00 | planned

依赖：FB-002 通过。
目标：形成论文级配对证据，不把不同数据集或不同变量的结果直接合并。

候选分支：

- **PAPER-A：项目/案例配对与 bootstrap**。
- **PAPER-B：Recall/FPR/F1/F3 与位置/机制族/精确 CWE 分层**。
- **PAPER-C：新增 TP/FP 的候选 lineage 和反馈来源追踪**。
- **PAPER-D：数据集、模型、预算、CodeQL、运行时和成本口径控制声明**。

最小验证：离线重算、配对键、分母、unknown 和失败状态检查。
中等抽检：固定一组完整配置和至少一个重复单元，生成论文表格草稿。
完成条件：预注册分析、独立 epoch、完整账本、统计区间和限制说明齐全。

## 分支状态速查

| 节点 | 状态 | 当前动作 | 失败回退 |
|---|---|---|---|
| COV-001 | completed | 保留基线 | 不回退 |
| COV-002 | in_progress | 优先 COV-002-B；并行可试 COV-002-A | ROOT/COV-002 |
| COV-003 | in_progress | 补逐 CWE、误报、成本与对照验收 | COV-002 |
| FB-001 | in_progress | 结构化反馈协议离线通过，待真实小样本 | COV-003 |
| FB-002 | planned | 等 FB-001 | FB-001 |
| PAPER-001 | planned | 等 FB-002 | FB-002 |

所有节点的实际结果必须追加到本文，不删除失败尝试；同一节点再次尝试使用新的尝试 ID、时间戳、冻结代码和 epoch。

## 核验更正 | 2026-11-10T12:47:40+08:00

此前 COV-003 completed 与 FB-001 中等协议抽检通过的判断过早，保留原记录作为历史说明：143 候选抽检仅表明候选级 supported 数量；30 请求是脚本合成、空证据和占位 snapshot，尚不能验证 B2→A3 交互、证据共享和语义去重。COV-003 回到 in_progress；FB-001 仍为 in_progress。

COV-002-C 后续 40 例及 120 例均通过流水线门槛，120 例组合 Recall 95%、FPR 23.33%，对照 80%、48.33%；中等集包含全部 40 例小样本，不能视为独立留出集。该结果只支持发现覆盖组合的阶段性收益。下一步补 COV-003 验收与 FB-001 契约缺口，通过后再推进真实 continuation。


## 收束检查点 | 2026-11-10T13:55:00+08:00

`BP-TREE-CHECKPOINT-20261110 | 2026-11-10T13:55:00+08:00 | completed`

- COV-002-C 的 `f6dc761` 已有 40 例和历史 120 例方向一致的组合增益；以 `c5ea14b` 截点集成源码及可重现流水线。锚点单项收益、逐标签复审和机制族一致性仍有缺口，COV-002/003 保持 in_progress。
- FB-001/002 已有开发草案，统一保存在 `codex/owasp-feedback-small-20261110` 的 `9f28785`。15 项离线契约测试通过，真实六例流水线尚未启动，闭环效果未知。FB-002 更新为 in_progress。
- 保留全部失败分支、旧 epoch 和此前核验更正；任何“技术通过”均不等于新增 TP。
- 不再启动中等或全量，不在本次收束中推进未验收分支。后续路线和证据索引见 [收束记录](benchmarkpython-consolidation-20261110.md)。
