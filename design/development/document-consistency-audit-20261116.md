# 文档过期与冲突扫描记录

核对日期：2026-11-16，北京时间。代码基准：main `954836c`。扫描使用当前工作区，包含此前已完成但尚未提交的启动文档去重改动；不是对该提交原始文档的纯净快照检查。

扫描前的可见文档共 **278 份：266 Markdown、10 DOCX、2 DOC**。对全体执行文件清点、字节摘要比较和 Markdown 本地链接初筛；对当前入口、疑似冲突项进行正文与代码交叉核对，提取全部 12 份 Word 文档正文，并补查测试方案 HTML。没有逐页检查 Word 排版，也没有重新核验外部论文或重新运行实验。

发现 **18 组需要更新、补历史标记或修复引用的问题**。没有发现字节完全相同的文档；多版方案和报告主要是内容重叠、版本关系不够清楚。本轮仅新增本扫描记录与本地机器清单，未删除或改写下述原文。

## 优先核对的当前说明

### DOC-AUD-001 系统说明中的默认阶段版本过期

- 位置：[system/README.md](../../system/README.md)，L20–21。
- 文档写新阶段默认 `review v4`、`Repair3`。
- 代码 [stage_execution.py](../../system/backend/app/contracts/stage_execution.py)，L11–20，实际默认值为 Scout 7、Review 12、Repair 4、Rule 8、Report 5。
- 建议：更新面向当前使用的版本说明；明确引擎选择与方法/Prompt 版本的区别。不能把默认 Repair 4 解释为默认启用 OpenHands，`RepairRequest.engine` 仍默认 native。

### DOC-AUD-002 系统说明中的预算和覆盖上限过期

- 位置：[system/README.md](../../system/README.md)，L49。
- 文档写默认最多 24 个窗口、24 批和 24 次调用，继续受阶段总预算限制。
- 当前 [ScoutRequest](../../system/backend/app/contracts/scouting.py)，L17–21，默认 `max_units=0`；[ReviewRequest](../../system/backend/app/contracts/stages.py)，L19–20，默认 `max_batches=0`。0 表示调度全部符合范围的单元，并不保证最终完整覆盖。
- [policy.py](../../system/backend/app/adapters/ai/policy.py)，L29–33，在默认 progress 模式下为 Scout/Review/Repair 冻结 `max_calls=max_tokens=max_seconds=0`，保留局部和停滞限制。
- 建议：区分默认 progress、显式 bounded 和历史冻结策略，删除已经失效的统一 24 上限描述。

### DOC-AUD-003 架构总览同时混用旧平台架构和新科研边界

- 位置：[architecture.md](../architecture.md)，L25–34、L46–65、L72。
- 主流程仍只有 CodeQL → AI 复审，未表示独立 Scout 与 CodeQL 的并发发现及汇合；目录图仍将四阶段核心实现放在平台 services/workflows，后文却说明新任务经 bridge 调用 research public。
- L72 还写 CodeQL 仅在主机执行，与现有根目录 Compose 的可选 CodeQL 工具卷部署不符。
- 当前边界依据：[AGENTS.md](../../AGENTS.md)、[解耦交付摘要](backend-decoupling-delivery-20261113.md)、[科研实现说明](../../system/research/README.md)。双引擎科研执行位于 [dual_discovery.py](../../system/research/src/semflow_research/runtime/dual_discovery.py)。
- 建议：重绘当前依赖和发现流程；平台旧实现单列 legacy，不再与当前开发落点并排当作同一架构。

### DOC-AUD-004 产品流程没有区分独立发现与告警复核

- 位置：[product-workflow.md](../product-workflow.md)，L11–12、L22–27。
- AI 发掘仍笼统描述为从告警实例、安全关键操作或流程出发，未交代上传后的独立 Scout，以及它不得把静态告警当作初始锚点的边界。
- 与当前[双引擎说明](../../system/README.md)和[下一阶段 discovery 开发规格](agent-collaboration-implementation-20261116.md)的职责划分不一致，容易把互补发现重新实现成告警跟随。
- 建议：分别说明独立 Scout、统一 Review、人工决定和下游修复/规则入口。本文不是全篇废弃，证据与人工门部分仍有价值。

### DOC-AUD-005 contracts README 保留迁移初期的可用性结论

- 位置：[system/contracts/README.md](../../system/contracts/README.md)，L30。
- 仍写“迁移中的初版契约”，并笼统要求不要宣称独立科研链路可用。
- [research README](../../system/research/README.md)、[CLI README](../../system/research_cli/README.md)和[解耦 PR 记录](backend-decoupling-pr-20261115.md)已记录独立入口、wheel 安装和限定真实工具验收；同时仍保留真实项目修复/规则未通过等限制。
- 建议：按已交付的独立入口和明确未完成的验收分别表述，不能继续用迁移初期的总括句，也不能改成“三内核真实项目端到端全通过”。

### DOC-AUD-006 Repair3 专题的默认版本和预算公式已落后

- 位置：[repair3-progress.md](../archive/20261116-document-consistency/repair3-progress.md)，L5、L22。
- 仍写“新阶段默认版本 3”；本地调用预留写为 `(tool_limit + 4) * repair_attempts`。
- 当前默认阶段为 4；[audit_config.py](../../system/backend/app/core/audit_config.py)，L46–49，显式声明源码工具总量 24、初始 12、模型调用上限 36、候选次数 3；[repair_policy.py](../../system/backend/app/adapters/ai/repair_policy.py)冻结独立预算字段。
- 建议：将本文明确标为 Repair3 版本说明，补链接到当前方法与预算定义；保留旧版恢复语义。不要将旧预算公式复制回新实现。

### DOC-AUD-007 两份功能说明仍声称仅属于旧 Windows 独立副本

- 位置：[AI_CHINESE_REPORTS.md](../archive/20261116-document-consistency/AI_CHINESE_REPORTS.md)，L3；[REPAIR_VERIFICATION.md](../archive/20261116-document-consistency/REPAIR_VERIFICATION.md)，L3。
- 仍以 `D:/semflow-audit-ui` / `D:\semflow-audit-ui` 与“原项目保留”作为功能归属说明。
- 功能已进入本仓库；当前用户入口是完整 Docker 部署或主机调试。基础 Compose 尚不能执行隔离修复验证，边界见 [DOCKER.md](../../DOCKER.md)。
- 建议：删除当前操作说明里的独立副本限定，链接统一启动入口；修复验收说明必须指出运行环境要求。旧演示日期和结果留作历史证据，不冒充当前部署已验收。

## 导航和命令已经失效的说明

### DOC-AUD-008 目录规则仍在推介旧 Compose 启动方式

- 位置：[repository-layout.md](../repository-layout.md)，L33。
- 仍指导从 system 目录使用 `--env-file ../.env -p semflow-audit` 启动，未区分仅数据库与完整应用模式。
- 根目录完整 Compose 已是日常启动入口；此前去重已更新 README 等入口，这份目录规则还遗漏在外。目录树也没有展示新 contracts/research/research_cli/research_bridge 边界。
- 建议：运行说明改为引用 [DOCKER.md](../../DOCKER.md)；五目录迁移日期和文件映射保持原义，另补当前子包导航。

### DOC-AUD-009 两处当前导航仍使用已迁移的 benchmark-data 路径

- 位置：[development/README.md](README.md)，L17；[实验 runbook](../../benchmarks/experiments/runbook.md)，L8–13。
- 前者要求在 `benchmark-data/` 找全文与数据，后者把实验、隐藏评分和模型输入根目录写为 `benchmark-data/...`。当前根目录不存在该目录，材料入口已为 `benchmarks/`。
- 建议：导航改为当前路径；执行规程中的评分/生成隔离边界仍保留，具体历史路径可通过[迁移清单](../repository-file-map.json)追溯。不能只移动说明中的答案目录而放松隔离。

### DOC-AUD-010 legacy CLI 示例配置缺失

- 位置：[experiment-cli.md](../experiment-cli.md)，L16、L42–43、L51。
- 文档链接并调用 `benchmarks/configs/cli/scan-review.example.json`；当前工作区和 Git 跟踪文件中都不存在该路径。
- legacy 身份已经清楚标注，不需要整份删除；问题是示例不可直接执行。
- 建议：恢复与 legacy 执行器兼容的非秘密示例，或删除失效调用并明确示例未随仓库交付；日常科研仍导向 `semflow-research`。

### DOC-AUD-011 当前测试方案的 Markdown Word HTML 不再同步

- 位置：[测试索引](../../benchmarks/testing/README.md)，L15、L21–22；[方案 Markdown](../../benchmarks/testing/simple-three-module-test-plan.md)，L3；[方案 HTML](../../benchmarks/testing/archive/20261116-document-consistency/project-test-plan.html)；`benchmarks/testing/archive/20261116-document-consistency/项目测试方案说明_v2.2.docx`。
- Markdown 已追加 2026-10-13 的 Vul4Py/CQLLM 执行范围；Word v2.2 正文仍为 PatchEval/QLCoder，提取正文不含 Vul4Py、CQLLM 或该补充日期。索引仍称二者一致且 Word 为当前版。
- HTML 同样保留 PatchEval/QLCoder；其声明的源文档 SHA-256 为 `312ff16d928a20c5603a960f1a92538f81f0d582e2f2d3f0862fe17d24460d55`，当前 Markdown 实际为 `88830db348ff1b05ce7f8a0e4af810c8f2269bb6a20178a4b8836323f13fa06c`。
- 建议：先确定当前测试方案的唯一正文；Word/HTML 作为带源摘要的导出物同步生成。已有版本及排版收据不能原地改写成新的历史版本。

### DOC-AUD-012 测试计划的全量尚未启动结论过期

- 位置：[方案 Markdown](../../benchmarks/testing/simple-three-module-test-plan.md)，L3；[Vul4Py/CQLLM 全量计划](../../benchmarks/experiments/vul4py-cqllm-full-test-plan.md)，L3。
- 前者仍写两项尚未开始全量运行；后者的 10-15 校对仍写 CQLLM 全量未启动。
- [CQLLM 10-15 中期报告](../../benchmarks/reports/cqllm-paper-comparison-20261015-interim.md)，L3，已记录生成/编译 596/596；[Vul4Py 10-16 全量报告](../../benchmarks/reports/vul4py-repair3-full-performance-20261016.md)，L7–9，已记录 100 项结束、12 项正式评分、1 项联合通过。
- 建议：计划页只保留范围和链接到逐轮状态；不要把“已经运行”改写为“整体效果通过”。原批次报告保持原值。

### DOC-AUD-013 实验续接索引仍把旧状态文件当作统一当前入口

- 位置：[experiments/README.md](../../benchmarks/experiments/README.md)，L9、L19、L34。
- 仍将 `state.json` 作为执行状态权威，并列旧“下一项”；该 JSON 的更新时间为 2026-10-16，next_action 指向已结束的 Vul4Py 全量轮次。首页虽补了 11-02 机制研究入口，仍未导航到 11-16 Agent 协作阶段。
- 当前 AGC 权威状态已在[固定 BenchmarkPython TODO](../../benchmarks/experiments/benchmarkpython-improvement-todo-20261109.md)，并由[11-16 开发顺序](agent-collaboration-implementation-20261116.md)引用。
- 建议：按实验系列分列当前入口，明确 `state.json` 只管理其历史系列；不修改旧实验的完成/失败记录。

### DOC-AUD-014 规则重设计文档首尾的实现状态不一致

- 位置：[rule-generation-redesign-plan.md](archive/20261116-document-consistency/rule-generation-redesign-plan.md)，L3 与 L153–155。
- 开头写“尚未实现本方案”，尾部更新已记录受限 DetectorSpec、FrameworkSpec 和 162 次可比较请求的原型结果。
- 建议：开头改为历史方案、部分实现并指出剩余工作；保留尾部“不代表全部 R1/R2 完成”的限制。属于状态入口未汇总，不是整篇技术内容无效。

### DOC-AUD-015 解耦验收清单的开场仍写实际运行尚未执行

- 位置：[backend-decoupling-acceptance-checklist-20261113.md](archive/20261116-document-consistency/backend-decoupling-acceptance-checklist-20261113.md)，L5 与 L19–28。
- 开场仍写实际运行尚未执行，后面账本已列多个 completed，且后续章节和 PR 文档有实际运行证据。
- 建议：将开场明确标为清单创建时的说明，顶部链接最新账本。ACC-007 blocked、ACC-010 planned 等未完成状态不能因文案整理被改成 completed。

### DOC-AUD-016 RepoAudit 耗时资料有直接数字矛盾

- 文件：`competition/references/代码审计低/代码审计效率低.doc`。
- 提取正文第一段写 RepoAudit 单项目平均超过 **448 分钟（7 小时以上）**；紧接着编号 1 又写单项目平均 **0.44 小时**，即 **26.4 分钟**。如果不是不同实验设置，这两个“平均”不能同时成立；文件未解释设置差异。
- 建议：标为待核来源资料，停止直接引用该数字。需要回查论文的版本、统计单位及原表后再决定正确数值。本轮未联网核验，不判断哪个数值正确，也不评价其他论文速度。

### DOC-AUD-017 竞赛对照和校对资料包含大量迁移前绝对链接

- 代表：[阅读与实现对照](../../competition/deliverables/archive/20261116-document-consistency/阅读与实现对照.md)，L8–13、L42–45；[校对意见](../../competition/review/archive/20261116-document-consistency/作品报告校对意见.md)、[测试数据补充清单](../../competition/review/archive/20261116-document-consistency/测试数据补充清单.md)、[建议替换段落](../../competition/review/archive/20261116-document-consistency/建议替换段落.md)。
- 链接仍指向本机 `.local-workspace/zhejiang-competition-project/...` 或根目录旧 `backend/`、`frontend/`。本地链接初筛共找到这些竞赛资料中的 121 条当前无法直接解析的引用。
- 建议：若作为可继续使用的写作导航，另建映射导航或更新链接；若作为按哈希导入的原始材料，则保持原文并在索引标明历史资料。不要为了修链接破坏原始导入哈希。

### DOC-AUD-018 测试归档 README 的验证命令仍指迁移前目录

- 位置：[benchmarks/testing/README.md](../../benchmarks/testing/README.md)，L122–137。
- 写在项目根目录运行 `.venv/bin/python scripts/archive_test_results.py ...`；实际解释器和脚本位于 `system/.venv`、`system/scripts`。
- 建议：统一指明在 system 目录运行，或用根目录可解析的完整相对命令；冻结归档正文不改，更新的是仍供使用的操作入口。

## 内容重叠和已被替代的版本

以下是归档/导航候选，不等于可以删除。按现有协议，带哈希的冻结历史和原始成绩必须保留。

| 系列 | 已旧或重叠的文件 | 当前应采用的入口 | 建议 |
| --- | --- | --- | --- |
| 三模块测试方案正文 | `current-three-module-test-plan.md`、`project-test-plan-v3-superseded.md`、`simple-three-module-test-plan-v4.md`、`v4.1.md`、`v4.2.md`、`v5.md`、`v6.md`，均在 benchmarks/testing | `simple-three-module-test-plan.md` 及其后续执行范围补充；先处理 DOC-AUD-011/012 | 保留版本原件，索引只推荐一个当前正文。旧 v3 导航里的“当前正式 v4”也已过期，不代表 CQLLM 方案整体废弃 |
| Word 测试方案 | `项目测试方案说明_v1.0/v1.1/v1.2/v2.0/v2.1.docx` | 索引目前指定 v2.2，但它尚未同步新范围 | 五个旧版已在索引标为保留，属于正常历史版本；不要只按文件名最大就认为最新内容已对齐 |
| 作品报告 | `作品报告.docx` 与 `作品报告修订稿.docx` | 建议在 competition 索引明确指定修订稿或另一个正式交付版本 | 提取正文相似度约 96.57%，主要差异在 2.2.1 流程设计；不是字节重复。未凭文件名推断已经批准哪份交付稿 |
| 旧作品原稿 | `competition/source/作品报告原稿.docx` | 当前实现以代码与新稿为准 | 原稿仍有旧技术叙述的阅读记录；它是原始来源，应保留，不能当现行设计 |
| 五目录迁移与早期实现方案 | `workspace-migration*.md`、phase-one/phase-two 历史方案、superpowers 的 2026-10-11 规格与计划 | AGENTS、当前架构入口、解耦交付与 11-16 开发规格 | 部分已明确写“历史”，继续按专题保留；不因旧路径或旧默认值逐篇重写实验语义 |
| 10-09 冻结测试归档 | `benchmarks/testing/20261009-workspace-v1/v2/v3/` 下 54 份 Markdown | 测试归档索引与迁移映射 | 内容相似来自不同冻结版本；保持原始字节，不做通用去重删除 |

[project-directory-index-20261102.md](../archive/20261116-document-consistency/project-directory-index-20261102.md) 是有日期的旧磁盘快照，其“当前文件数/体积”只对当日有效；不作为本次清理依据。[progress-execution-20261013.md](../progress-execution-20261013.md) 中“修复继续 bounded”只适用于当时版本，现已被后续 repair 策略覆盖，适合补历史适用范围。

## 本地引用初筛的统计口径

按当前路径直接解析 Markdown 链接，得到 **421 条未解析候选，分布于 55 个文件**：

| 所属范围 | 条数 | 解读 |
| --- | ---: | --- |
| 10-09 冻结归档 | 264 | 旧路径和本地收据引用；需结合迁移映射，不能当作原始证据丢失 |
| 竞赛导入资料 | 121 | 主要是迁移前本机绝对路径；见 DOC-AUD-017 |
| 上游数据集原始 README | 12 | 相对上游仓库的链接，不应直接改写为本项目当前路径 |
| 其他 | 24 | 包含旧方案数据路径、本地忽略产物、带行号的旧代码引用和缺失 legacy 示例；需逐项判别 |

这是初筛候选数，不是 421 个已确认应修复的死链接，更不证明对应产物在所有机器上均不存在。原始收据/资料的哈希保持约束优先于通用链接修复。

机器清单保存在本地忽略目录：

- `artifacts/local/doc-audit-20261116/reference-scan.json`：文件格式计数、摘要去重结果、421 条引用候选的位置与目标。
- `artifacts/local/doc-audit-20261116/word-inventory.json`：12 份 Word 原件的路径、SHA-256、正文长度与开头摘要。

## 本轮处理结果

根据本清单已完成一轮文档收敛：

- 当前入口已修正默认版本、Docker 端口、双引擎职责、实验状态和主机路径说明。
- 新增根目录 `一键启动-Docker.sh` / `一键停止-Docker.sh` 与 `一键启动-Docker.cmd` / `一键停止-Docker.cmd`，统一调用完整 Compose。
- 明确属于旧版本或过期导出的设计、测试方案、Word/HTML 导出、早期竞赛稿和数字冲突参考资料已移入各自的 `archive/20261116-document-consistency/` 目录；原文仍可追溯。
- 未改实验结果、数据库、代码算法或真实模型产物；未运行真实模型或付费任务。

本记录保留初始扫描事实和原问题编号；后续新增问题使用新扫描日期和新记录，不覆盖本次审计。
