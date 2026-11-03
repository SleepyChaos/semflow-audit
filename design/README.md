# 开发设计文档索引

以功能与模块边界为依据实现四阶段审计链路；阶段间传递持久化 ID 和产物引用，保留不可变输入与执行历史。

| 入口 | 内容 |
| --- | --- |
| [architecture.md](architecture.md) | 模块边界与架构 |
| [product-workflow.md](product-workflow.md) | 功能链路与界面流程 |
| [repository-layout.md](repository-layout.md) | 五个主目录与归档规则 |
| [目录现状与精简候选](project-directory-index-20261102.md) | 实际目录、文件数、空间占用、可再生成项与结构简化建议 |
| [双引擎开发计划](dual-engine-development-plan.md) | 静态扫描与独立 Agent 发现 |
| [审计三机制详解](audit-mechanisms-20261102/README.md) | 互补发现、前提复审与反馈补证；日志证据、收益来源及DVGA本地修复 |
| [业务语义修复](semantic-repair-plan.md) | 修复编排与验证设计 |
| [规则双库设计](rag-two-corpus-plan.md) | reference / rule_example 集合与索引 |
| [规则稳定化计划](rag-stabilization-phase-plan.md) | 生成、证据、编译与验收边界 |
| [修复与规则改造计划](repair-rule-development-plan.md) | 后续开发任务 |
| [LLM中段介入设计](development/codeql-intermediate-llm-design.md) | CodeQL 分析阶段协同 |
| [下一阶段计划](development/phase-two-master-plan.md) | 规则生成、审计效果与速度 |
| [验收清单](acceptance-checklist.md) | 功能与人工验收要求 |
| [上游来源](upstream.md) | 框架与模板来源 |
| [原工作区迁移说明](workspace-migration.md) | 既有迁移背景 |
| [本次逐文件迁移清单](repository-file-map.json) | 旧路径、新路径与哈希 |
| [迁移验证收据](repository-reorganization-verification.json) | 测试、构建、数据恢复与历史归档校验 |

`development/` 保存研发过程中产生的专项设计与计划，`design/` 保存既有工作台概念图。实测结果集中在 [benchmarks](../benchmarks/README.md)，文献阅读记录集中在 [research](../research/README.md)。
