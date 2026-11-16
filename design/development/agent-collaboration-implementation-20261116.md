# Agent 调查与协作：下一阶段开发顺序

计划记录：AGC-PLAN-20261116 | 2026-11-16T18:26:38+08:00 | completed。
本 completed 仅表示开发顺序已整理；14 个实施任务仍按[主 TODO](../../benchmarks/experiments/benchmarkpython-improvement-todo-20261109.md)登记，不在本文重复维护状态。首次整理依据 main `f48108f`，包含 `82f0c35` 的研究 TODO 和归属索引；算法基线仍为 `f92f227`。本文件是 discovery 的开发规格和交接入口。

## 1. 本阶段目标和职责

先改善两个现有 Agent 的调查与证据交接，形成可恢复的一次 Review→Scout→Review 往返。Scout 提出假设并追踪事实，Review 提出缺口并核对返回证据；协调器使用确定性规则。共同维护的是待证问题、来源明确的观察和不可变结果，不是不断扩大的公共聊天历史。

本阶段以 Python 既有案例检验机制。固定小样本出现可追溯进展后，再决定 CodeQL 的共同分析缺口和约两类目标漏洞。第三 Agent、规则模型自动生成、发布和平台 GUI 扩展需要后续范围决策。

| 改进归属 | 实验内核模块/其他部位 | 责任与提交分区 |
| --- | --- | --- |
| 实验内核 | discovery：Scout、Review、协作编排、证据门 | core-discovery；对应实现、包内测试及直接说明随本分区提交 |
| 共享契约 | 任务、收据、策略与类型/Schema | contracts；只表达协议和结构约束 |
| 实验 CLI | public 请求参数装配和结果查看 | experiment-cli；没有第二套调查算法 |
| 独立评测 | 固定样本、对照、预检、评分与验收报告 | benchmarks；答案/参考补丁不进入模型上下文 |
| 平台兼容 | 仅在请求映射变化确有需要时单独安排 | platform-bridge；本阶段先保持既有方法的正常路径 |

## 2. 已核对的实现入口和设计约束

| 当前文件（相对 system/） | 已有行为 | 对开发顺序的影响 |
| --- | --- | --- |
| research/src/semflow_research/public/discovery_requests.py | CLI/Web 共用冻结装配；默认 Scout 8、Review 12；有调用/窗口/复审开关 | 显式新方法与新策略入口先设计，保持旧默认和历史含义 |
| research/src/semflow_research/runtime/dual_discovery.py | 固定 scan/scout 后 review，一次合并；编排版本仅接受 1 | 协作作为显式新方法接入，不能静默改变版本 1 |
| research/src/semflow_research/runtime/children.py | 每个父执行对 scan/scout/review 各绑定一个固定 child ID | 不能用相同 review/scout ID 重跑不同输入；多轮身份方案是 PRE-001 的必要决策 |
| contracts/src/semflow_contracts/results.py | BranchOutcome.branch 只允许 scan/scout/review | 角色与反馈任务/轮次分别表达；禁止随意增加 branch 字符串绕过类型 |
| research/src/semflow_research/discovery/scout_inspection.py | 窗口内工具循环；重复读取轨迹可能触发 final-only；强定位约束 | 先单独验证新循环策略，首轮窗口归属与定向追踪的跨文件候选范围分别声明 |
| research/src/semflow_research/discovery/review_batch.py、review_feedback.py | 批内工具循环、剩余预算补证、历史初评保留 | 复用引用/前提门；不要把已有补证包装成首次实现反馈 |
| research/src/semflow_research/adapters/review_evidence.py | 从缺失前提文字提取文件路径，复用同执行页或读取源码 | 增加符号/关系级任务表达；已有证据检索和新调查区分路由 |
| research/src/semflow_research/runtime/scout_continuation.py | 冻结地图的未完成窗口续接，禁止变更原调度/身份 | 新定向追踪不是旧窗口续接，不得借旧 continuation 字段改变语义 |
| research/src/semflow_research/public/discovery.py、runtime/bundle_io.py | 公开执行边界、显式叶生产者、冻结 bundle 与输入证据校验 | 新证据和任务输入继续走类型化引用；不能读取其他执行的可变工作目录 |
| research_cli/src/semflow_cli/discovery_commands.py | options/resources 经 public 装配执行 | 优先复用 discovery-discover 和 options，不先造另一套命令框架 |

上述是本轮源码核对，不等于 PRE-001 全部完成：旧分支差异、具体版本/身份方案和复用决定仍需交付。当前工作树未安装独立 system/.venv；后续实际命令先按锁文件准备隔离环境，本轮没有宣称测试通过。

## 3. 分批开发顺序和每批退出条件

### 批次 A：前置事实和最小验证输入

对应 PRE-001、PRE-002、PRE-003。

1. 补齐 main/旧反馈分支差异，核对可复用函数、Prompt、测试及预算历史；不直接 cherry-pick 含 app 依赖的旧实现。
2. 给出两项设计决定：新的方法/策略版本组合；同一父执行中初评、追踪、复评的不可混淆身份。若采用任务子执行，扩展版本化绑定而保留旧 child_id；若采用内部检查点任务，明确预算/产物归属，不能伪装成旧已完成子执行。
3. 固定六任务，包含可补证、反证、无进展/政策未知，每类至少两个；尽量跨三个项目。同一项目案例不冒充独立项目。新候选产生可以与其中任务交叉覆盖。
4. 分开准备生成输入与 evaluator 真值，冻结选样理由、四组比较、成本上限与失败处理。新实现的最终代码/Prompt 摘要等技术门通过后补齐。

交付：源码调用链/差异与身份决定、任务输入清单、独立参考事实、实验预检协议。案例来源或参考裁决缺失时记录具体缺口；可以继续不依赖该材料的设计和单元验证，但不能运行效果实验。第一笔代码从批次 B 开始。

### 批次 B：最小任务契约

对应 CON-001；先做 `contracts` 提交，再做消费方实现。

候选类型命名供设计使用，最终 API 名称在 PRE-001 冻结：InvestigationTask、InvestigationReceipt、CollaborationPolicy。任务至少表达快照/执行/方法身份、候选引用或覆盖义务、待证命题、缺口类型、目标符号/位置、允许动作、证据要求和预算引用。收据表达 answered/contradicted/unresolved/failed 等任务结果、观察、证据及边界和可选新候选引用；最终漏洞评估仍使用既有结论协议。

区分三种状态：任务执行状态、命题是否被证据回答、漏洞评估结论。工具执行成功不等于命题已回答，命题已回答不等于漏洞成立。已有事实复用记录实际来源与当前授权，模型解释不直接进入事实账本。

幂等键必须基于原快照、语义目标、动作参数和方法版本，不能包含随机 request_id 后声称语义去重。关联 evidence/task 引用经过实际 bytes 与来源权限校验。契约声明只校验结构/协议，语义策略仍在 discovery。新增字段或默认值不能在解析旧冻结请求时补写回去并改变 input_digest；序列化兼容和旧请求摘要用固定历史样例验证，必要时使用显式新版结构。

退出条件：合法正反例、身份漂移、越界、未知版本、无证据确定结论、重复任务、旧协议只读兼容均有对应验证。公共声明与发送/接收端注释同步标注；contracts commit 必须结构自洽。

### 批次 C：先完成单 Agent 调查循环

对应 CORE-001，归 `core-discovery`。

保留现有工具结果回填和证据门，增加显式调查目标/剩余缺口/停止原因。区分重复读、读取失败、得到新页、从已有页核实新关系；不能因为一次缓存命中立即禁止其他合法调查。也不能仅因为模型换了措辞就认定有进展。

先增加能复现问题的测试，再改新版本策略。停止规则保持有限预算和 no-progress 上限；原窗口检查仍限定原候选归属。定向追踪的新候选可以位于授权范围内其他文件，需独立追踪任务身份和证据，不能放松普通窗口方法的定位门。

退出条件：有剩余预算时允许“缓存命中后读取新事实”；连续无进展/预算耗尽正确停止；源码/上下文超限不截断成伪证据；未知、取消和已保存发现保留。此批应可单独回归，不等待完整协作。

### 批次 D：两端各自实现任务生产和消费

对应 CORE-002、CORE-003，分别提交 `core-discovery` 的完整行为切片。

先实现 Review 任务生产：明确缺失事实和验收要求，对已有页装配、关系追踪、缺静态模型、不可得政策分别分类。已有结果未经过任务前不被覆盖；缺静态模型只登记未解决原因，第一版不自动生成/发布规则。

再实现 Scout 任务消费：根据显式问题使用工具，返回可核查观察/反证/仍未知。旧发现候选和反馈产生候选保持不同身份；新候选经过同样引用/定位门，新增但未复审者保持 unknown。证据只共享必要事实、引用及有限背景，不把对方结论当事实。

退出条件：两端可以用冻结任务/收据分别验证。原候选支持、被反证、继续未决和新增候选均可解释；文件名未知但符号可搜索的任务可调查；业务政策未知不会变成“没有漏洞”。

### 批次 E：确定性协调和一次完整往返

对应 CORE-004，归 `core-discovery`。

将两端接入显式新 discover 方法；Review 提交缺口后，协调器优先复用证据，必要时调用 Scout 追踪，之后针对返回事实复评。首版每任务最多一次定向往返，不要求用满配额。不因角色切换获得新的 token/call/time 配额。

先验证最小纵向切片，再补恢复与失败。初评、任务、工具调用、返回证据和复评均追加记录；重启恢复从检查点继续。无法判断提供商是否执行过的调用沿用未知结果拒绝盲重放原则。只有经过校验的 manifest/bundle 可供后继执行读取。

退出条件：复评只改变有新证据依据的对象；兄弟候选不被误改；同任务幂等重放不增加物理调用；父子预算不超额；任一步失败仍能查看初评和部分证据。首轮 CodeQL/Scout 独立性及旧方法正常路径通过回归。

### 批次 F：独立 CLI 和组合技术门

对应 CLI-001、TEST-001。先 `experiment-cli` 提交薄装配，再 `benchmarks` 提交组合验收入口/报告。

现有命令通过 options 显式选择新方法和反馈上限，public 负责机械引用装配。新接口在入口声明、实际发送/接收和 capabilities 同步；旧 CLI/Web 不自动启用新算法。若平台映射必须改动，另开 platform-bridge 任务和提交。

在仓库外新进程运行正常 public 业务链，禁止导入 app/Web/ORM/队列；保留源码范围、原始请求、执行/manifest/任务关联、用量和退出码。G1 使用明确标记的模型/工具替身完成可控失败验证，再与真实模型效果分开记录。

### 批次 G：六任务对照和后续选题

对应 EXP-001、GATE-001；G2 通过后才执行 SCOPE-001、SCOPE-002。

四组方法、G1/G2 具体门槛以主 TODO 为准。本计划不修改门槛。第一次效果实验前冻结最终代码、方法与 Prompt、输入/参考事实、模型身份、CodeQL/pack/suite、预算和 epoch。最多一个开发重复单元，不将重跑中最好的一次当主结果；需修改则新 attempt ID 并保留原结果。

实验先读取流水线验收表，异常才查细日志。失败、超时、unknown 保留分母；分别报告原候选裁决变化和反馈新增根因，不能以 CWE 标签变多当新增漏洞。

G2 有进展后，范围选择按“共同 CodeQL 缺口→对应两类漏洞→独立正反例”的顺序。需要查清原生能力、构建/提取范围、库/调用关系及静态事实的独立作用；没有共同缺口时保持未定，不强定弱随机数/弱哈希或 JS。第三 Agent 和 rules 模型补全由专项证据决定。

## 4. 既有验证入口和后续命令

下列为后续准备好锁定环境后的计划命令，工作目录为 `system/`，本轮未执行。包内新测试随各批次增加，不能只跑旧测试证明新功能。数据库/真实 CodeQL 用例按标记、显式资源与隔离条件执行，不把缺资源直接转为成功。

```sh
uv run --frozen python -m pytest contracts/tests/test_contracts.py -q
uv run --frozen python -m pytest research/tests/test_discovery_execution.py research/tests/test_dual_discovery.py -q
uv run --frozen python -m pytest research_cli/tests/test_independence.py -q
uv run --frozen python -m pytest tests/test_research_discovery_bridge.py tests/test_research_review_bridge.py tests/test_research_scout_continuation.py -q
```

`tests/test_review_feedback.py` 等旧平台用例用于了解原有语义，不能替代 research 包新实现的测试。工具/模型替身、真实工具与真实模型结果必须分别记录。新包边界和新任务状态还需专门新增 public 验收用例。

## 5. 提交与交接规则

顺序为：前置评测协议 → contracts → 单 Agent loop → Review 任务 → Scout 任务 → 协调器 → CLI → 组合验收/效果报告。相邻同分区也按可独立审查的行为切片提交；跨区不混合、不 squash。文档和迁移说明同步对应字段与历史策略。

实施者每次开始读主 TODO 当前表和本计划，结束更新主 TODO/改进树实际任务时间、状态、证据与 outcome；本文件仅在实现选择改变时更新设计。每项完成必须列明验证范围和未执行项。下一步明确为 **PRE-001 的旧分支核对与新执行身份决定**，随后完成六任务事实裁决和预算预检。
