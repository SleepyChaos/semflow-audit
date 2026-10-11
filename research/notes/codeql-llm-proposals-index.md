# LLM 与 CodeQL 协同方案索引

保存确认日期：2026-10-09。状态：研究与设计已保存，尚未作为本轮开发任务实现；历史审计实验结果保持原口径。

## 方案清单

| 方案 | 核心机制 | 当前建议 | 详细文档 |
|---|---|---|---|
| 条件化分析模型精化 | LLM 提出带版本、配置、分支条件的模型；CodeQL 核查绑定与路径影响，反馈修订 | 优先研究；显式区分假设与已核验事实，严格约束会删除告警的屏障 | [研究方向](codeql-llm-interaction-research.md) |
| 业务权限关系检查 | LLM 提出主体、动作、资源及权限条件；CodeQL 检查对象关系和保护覆盖 | 第二阶段候选，先限所有权与租户隔离 | [研究方向](codeql-llm-interaction-research.md) |
| 路径反证与约束核验 | 固定结构分析、局部 LLM 理解与受限约束转换，必要时交给求解器 | 核验组件；未知不当作安全 | [研究方向](codeql-llm-interaction-research.md) |
| 在数据流分析中介入 LLM | 诊断查询输出语义需求；LLM 补转换/保护事实；GlobalWithState 传播并检查，分轮迭代 | 最具体的优先试点，是条件化模型方案的落地方式 | [中段介入设计](../../design/development/codeql-intermediate-llm-design.md) |

## 已保存的研究内容

- 相关论文、已有机制和创新边界：IRIS、SemTaint、ARQ、LLM4PFA、Artemis、ABSENTIA、APAS-Finder。
- 当前源码中的并行分支、已发布规则查询工具、窄范围模型扩展及其能力边界。
- CodeQL 外部事实、状态转换、状态相关屏障的接口；本地 CLI 2.23.5 与固定库核查。
- 局部源码、资料、证据引用及未决前提的上下文输入边界。
- 试点范围、同预算基线、分量消融、跨项目迁移与失败/成本指标。

## 实施前的关键边界

- 官方外部谓词导入不是实时 LLM 回调；当前设计在查询之间分轮协同。
- 新模型只有被相应查询使用才生效，不自动修改整个官方 suite。
- 条件化模型与状态介入是同一研究路线的不同层次，不能重复计作两个独立创新。
- 状态分析、外部 CSV、LangGraph 和 RAG 是已有组件；方法创新需要独立实验验证。
- 当前只保存研究方案；不因本次归档更改生产链路或启动付费模型测试。

## 本地目录

- 当前开发仓库：`/Users/chaos/Documents/GitHub/semflow-audit/`
- 当前会话工作区入口：`/Users/chaos/Documents/Codex/2026-09-29/xin-j/`；旧项目路径保留兼容链接。
- 研究与方案：仓库中的 `docs/research/`
- 基准材料与实验管理：仓库中的 `benchmark-data/`
- 审计及实验产物：仓库中的 `artifacts/`
- 外部工具与临时研究依赖：仓库中的 `.local-workspace/work/`（仅本地）
- 会话输出目录：仓库中的 `.local-workspace/outputs/`（仅本地）

新仓库：`https://github.com/SleepyChaos/semflow-audit`，私人仓库。旧 `ai-code-audit` 保留为历史来源；本轮迁移进度见[迁移说明](../../design/workspace-migration.md)。
