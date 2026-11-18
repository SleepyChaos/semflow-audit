# 证据感知复审改造前审计

审计时间：2026-11-19，北京时间。基线：个人分支 codex/personal-development，提交 2a74e0a2b433745b23dd38fc2c5823c8df64174e，工作区干净。仓库已实现的 PR #5 功能早于本文，不能将 8abb6a8 当成现状。已检查根 AGENTS.md 和被 Git 跟踪的子目录规则，当前仅有根文件。

| 核查项 | 当前实现与边界 |
| --- | --- |
| 双分支 | runtime/dual_discovery.py 创建 scan、scout 子执行；CodeQL 通过 adapters/codeql/sarif.py 保留告警、位置与线程路径。Scout 从独立源码窗口产生候选。CodeQL 空结果不排除 Scout 发现，路径不是可执行性的形式化证明。 |
| 身份 | 静态发现由快照和原始告警 ID 派生 UUID；候选同时有执行内 UUID、identity_key、原候选 derived_from，平台另投影 UUID。Review 子执行候选仍保留来源，不能用标题或行号代替身份。 |
| 合流 | runtime/discovery_merge.py 和 bundle_io.py 合并可验证的叶子产物，冻结候选和证据范围。缺失叶子、未复审候选保留覆盖缺口。 |
| 上下文 | review_pool、review_tools 和 discovery_context 提供目标页、相关本地导入、小型模块、项目文档与 CodeQL 路径；v12 通过读取、搜索等受限工具取证。项目快照可读范围与模型上下文分别校验。 |
| v12 输出 | 现有 verdict、checked_premises、missing_premises、premises、runtime_unknowns、evidence_ids、counterevidence_ids、security_property、detail、根因关联均保留。supported 表示模型证据支持缺陷，excluded 需要反证，pending 表示尚无定论，insufficient 表示必要前提未齐。 |
| 补证与恢复 | review_feedback 从缺失描述找文件，用原批次剩余预算补读；review_recovery 对已调度但遗漏的候选有界恢复。现有跨执行续审区分剩余源码、任务重试、补材料与人工定位，并保留原记录。 |
| 持久化 | LocalLedger 和内容寻址 LocalArtifacts 保存输入、清单、调用、证据包和结果；快照源码页、命中位置、SARIF、候选、反证和结果已有可靠引用。 |
| 逐候选缺口 | AssessmentBundle 只含模型通过校验的判断。未评估项和运行停因在 coverage 与诊断 trace，尚无统一公共逐候选记录。退回的引用有诊断但不应投影为事实。 |
| 平台 | research_bridge 读取公共产物、映射执行和证据 ID，工作台展示模型结论和下一动作；Decision 仍由独立人工接口记录。 |
| 兼容 | ResultEnvelope、DiscoveryResult、CandidateBundle、AssessmentBundle、EvidenceBundle 和已有冻结 RunSpec 输入不得破坏历史摘要或语义。诊断 trace 保留已有字段；新结果作为可选版本化产物。 |
| 缓存缺口 | 同次源码页及跨轮候选证据已可复用，但缺显式事实缓存身份、验证版本、失效和对照计数。已检查文本不等同于独立证明的程序事实。 |
| 测试 | 代码修改前固定回归 49 passed，包括 contracts、科研复审与双分支、独立 CLI、平台桥接。测试使用本机 Python 3.14、独立临时目录、工具与模型替身；不视作真实模型、全套生产数据库或检出率验收。 |

与 design/development/backend-decoupling-pr-20261115.md 及 design/discovery-semantic-improvement-plan.md 的历史设计对照，后端依赖边界继续保留。上个 Flask 真实模型样本有超时与政策缺证，不能作为精度或节省调用的基线收益。
