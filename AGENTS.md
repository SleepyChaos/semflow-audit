# 协作者 Agent 协议

## 1. 仓库目录与用途

以 `design/` 的功能、契约和模块边界为依据维护审计链路；开发命令通常从 `system/` 执行。下列 core 是职责名称，不要求重命名现有目录；`backend/app/core/` 是平台配置，不是科研内核。

| 目录 | 用途与归属 |
| --- | --- |
| `system/research/src/semflow_research/` | 实验内核 core：`discovery/` 双引擎漏洞发现及统一复核；`repair/` native/OpenHands 修复、测试集与前后验证；`rules/` RAG QL 生成及技术检验。`public/` 为对外入口；`adapters/`、`ports/`、`runtime/`、`state/`、`evidence/` 等提供科研支撑，`graphs/`、`prompts/` 按所属内核归类。 |
| `system/contracts/` | 独立、共享的类型声明与 JSON Schema；不包含算法或平台业务。 |
| `system/frontend/` | 平台前端：交互、状态、源码与 Diff 展示。 |
| `system/backend/app/` | 平台后端：API、任务、应用编排、持久化、展示与人工事务；`alembic/` 保存迁移。 |
| `system/backend/app/research_bridge/` | 平台兼容层：输入冻结、调用 research public、ID/产物引用转换与结果投影；不实现算法。旧 `services/`、`workflows/`、`runtime/`、`cli/` 中仍有历史兼容代码，不能据此扩展新算法副本。 |
| `system/research_cli/` | 独立实验 CLI，直接调用 research public；旧 `app/cli/` 属于平台历史兼容入口。 |
| `system/agents/`、`system/runners/` | 独立工具运行时、固定 SDK 依赖及隔离验证镜像；不是第四套业务内核。 |
| `system/scripts/`、`system/tests/`、各包 `tests/` | 初始化、工具/评测脚本及测试；测试按被验证职责归属。新科研执行脚本使用 public/独立 CLI，冻结历史脚本保留原行为。 |
| `system/knowledge/`、`system/pyproject.toml`、`system/uv.lock` | 生产知识种子、工作区依赖及锁文件；各独立运行时另有自己的锁文件。 |
| `benchmarks/` | 数据集、评测输入、协议、实验记录与结果；评分/隐藏答案不进入生成上下文或生产知识库。 |
| 根目录 `research/` | 论文、阅读笔记与方法研究资料，**不是** `system/research/` 实现包。 |
| `design/`、`TODO/` | 架构、开发/验收计划与专题待办；按已有主题入口维护，不重复开清单。 |
| `competition/` | 作品报告、模板、配图与交付资料。 |
| `artifacts/`、`system/artifacts/`、`.local-workspace/`、`output/`、`tmp/` | 本地运行产物、展开数据、渲染与临时文件；不作为源码提交，不能假定全部已被 Git 忽略。 |
| 根目录配置与 `.github/` | README、AGENTS、许可、Git/部署配置及 CI；`.env`、本地环境、真实上传和审计产物不入库。 |

## 2. 开发协议：保持三类代码解耦

- **依赖方向**：实验 CLI → `research.public` ← 平台兼容层 ← 平台后端；前端只调用平台 API。双方共享 `contracts`；contracts 只声明类型、结构校验与协议，不反向依赖任何业务包、ORM、Web 或图框架。不得通过内部模块、动态导入、HTTP 或目录约定绕过边界。
- **实验内核**：发现、修复、规则各自拥有算法，跨模块传递类型化输入与产物引用，不直接修改对方执行状态。内核及其适配器不得依赖 `app`、CLI、平台 ORM/Web/Celery、User/Workspace/StageRun、平台数据库或 `.env`；资源、范围、预算、模型/工具/语料配置显式注入。共享代码只放真正通用的科研支撑模块。
- **平台系统**：后端保留归属、任务调度、人工确认、接受/发布及事务；前端负责交互展示；兼容层仅做契约转换、public 调用与投影，不重做科研判断、调用内部图或复制 Prompt/算法。平台后续任务不得由算法 finalize 调用 API/Celery 自动投递；服务不得反向依赖路由。投影重试不得重跑模型。
- **实验 CLI**：只依赖 contracts、research public 和自身命令装配；无需安装/启动 Web、平台数据库或 Redis。不得复用旧平台 CLI/runtime 冒充独立入口，也不在 CLI 中实现另一份算法。
- **契约与历史**：阶段间使用持久化 ID、不可变快照和 ArtifactRef，不传 ORM/Session，不依赖可变上游工作目录。区分平台 ID 与科研 ID、方法版本与 Prompt 版本、不同摘要算法；新执行冻结版本，历史执行保持原 executor/checkpoint，未知版本明确拒绝。
- **接口联动**：关键 JSON 的字段、默认值、状态、身份和摘要语义写在类型/Schema 与实际发送、接收端注释中，注明对端位置及“Agent 修改时同时核对另一端”。修改时同步声明、两端和兼容测试，必要时升级版本/语义修订；普通 JSON 不写注释，不以本文件代替接口注释。
- **证据与人工门**：LLM 输出先校验结构，再校验证据；模型支持不等于人工确认，技术通过不等于接受补丁或发布规则。失败不得伪装为成功空结果，未评估不得默认排除；无独立检验不得宣称整体验收通过。保留失败、部分结果、用量与执行历史，隐藏检验内容不得进入生成/RAG/反馈。
- **实现纪律**：按职责拆分，复杂函数拆为具名步骤，不机械碎片化。手写文件通常 150–300 行，超过 400 行检查职责，超过 500 行默认拆分或说明理由；生成文件除外。路由、图节点、任务入口保持薄，外部命令、SARIF、检索和模型接入放适配器；Prompt 独立版本化。不增加膨胀的 utils.py 或全局共享可变业务状态。优先成熟框架，仅在证据、确认和验收等必要边界自研；首次引入固定版本并提交相应锁文件。
- **验证**：测试任务隔离、失败状态、真实证据关联、规则正反例及契约兼容，不能只测函数存在/空列表。边界变动验证 CLI 无平台依赖、Web/CLI 共享 public；如实区分替身、真实工具、真实模型和未执行项，不以导入成功或局部通过冒充完整验收。
- **待办与实验**：TODO/改进树节点均保留稳定 ID、北京时间时间戳和状态（`planned`、`in_progress`、`blocked`、`completed`），状态变化更新对应时间，如 `BP-FB-001 | 2026-11-09T10:55:01+08:00 | planned`。BenchmarkPython TODO 固定在 `benchmarks/experiments/benchmarkpython-improvement-todo-20261109.md`，改进树固定在同目录 `benchmarkpython-improvement-tree-20261110.md`。仅做固定小样本，通过流水线验收才进入子节点；失败保留产物并回退上游，扩样/全量另行安排。重复节点使用新尝试 ID、冻结代码与 epoch，不覆盖历史结果。

## 3. Commit 分类与提交规范

使用 `type(scope): 具体变更`，type 取 `feat`、`fix`、`refactor`、`test`、`docs`、`build`、`ci`、`chore`；破坏兼容的变更用 `!` 并说明迁移方式。scope 按实际职责而非文件所在目录决定：

| 分区 | scope |
| --- | --- |
| 实验内核：发现 / 修复 / 规则 / 公共支撑 | `core-discovery` / `core-repair` / `core-rules` / `core-shared` |
| 共享数据契约 | `contracts` |
| 平台：前端 / 后端 / 兼容层 | `platform-frontend` / `platform-backend` / `platform-bridge` |
| 实验 CLI | `experiment-cli` |
| 独立评测 / 仓库文档协议 / 部署与工具设施 | `benchmarks` / `docs` / `infra` |

- **一个 commit 只包含一个分区的一项完整变更。** 内核、平台、CLI 必须分开；三个内核之间、平台前端/后端/兼容层之间也必须分开。不得用 `core-shared`、`infra` 或泛称重构打包跨区改动。
- 例如同时改 Web 前后端，提交 `feat(platform-backend): …` 与 `feat(platform-frontend): …` 两次；若还改桥接、契约或内核，再分别提交。单个 PR 可以包含这些有明确依赖顺序的 commits，不能靠 PR 描述代替拆分。
- 同分区的实现、对应测试和直接配套说明可同次提交；公共契约、共享依赖/锁文件、仓库级协议单独提交。同一文件跨分区修改须按职责/hunk 暂存，无法清晰划分时先理清边界，不能直接混合提交。
- 提交前检查 status、暂存 diff 与测试结果，精确暂存本次内容；不得夹带其他协作者改动、无关格式化、密钥、真实上传、审计产物或临时文件。不重写冻结实验历史，不以提交为由擅自清理工作区。
- commit 正文/PR 说明写明问题、行为变化、契约/迁移影响、验证范围及失败/跳过项；跨区 commits 说明依赖顺序，最终组合完成相关检查。合并时保留分类提交，不将跨区 PR squash 成一个混合 commit；提交、推送、合并遵循用户授权，不掩盖失败或绕过检查。
