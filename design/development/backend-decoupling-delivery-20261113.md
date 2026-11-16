# 后端解耦交付摘要与后置清单

后续现场验收及真实项目联通结果见[操作验收清单](archive/20261116-document-consistency/backend-decoupling-acceptance-checklist-20261113.md)，合并范围和未通过事项见[PR 交付记录](backend-decoupling-pr-20261115.md)。以下 S6 completed 只表示当时的代码边界验收，不代表全部运行验收通过。

S6 | 2026-11-13T11:22:31+08:00 | completed。本次代码交付和 S1～S5 限定验收 completed；S6 的状态/边界固化已完成，轻量检查 23 passed。`implemented` 表示双端边界已验收，未宣称模型效果提升；实际平台实例未部署、数据库未迁移。

| 已交付切片 | 独立 CLI | 平台入口 / 科研 public |
| --- | --- | --- |
| Discovery | discovery-scan / discovery-scout / discovery-review / discovery-discover | 上传扫描、双引擎、Scout、Review → research_bridge scan_runtime/runtime → public.discovery.execute |
| Native repair | repair-native / repair-build-suite / repair-verify | RepairPanel、suite、复扫、前后比较 → repair_runtime → public.repair.execute |
| OpenHands repair | repair-openhands；复用 inspect/cancel | RepairPanel 的 OpenHands 分支 → repair_runtime → 同一 public.repair.execute |
| RAG rules（method 8） | rule-generate / decide / resume / rule-validate | approve-fixtures→原图 resume→confirm-project-match→publish → rule_runtime → public.rules.execute/resume |

CLI 仅依赖 contracts 与 research public；Web bridge 仅做冻结输入、ID/ArtifactRef 转换、投影与平台权限/人工事务。模型判断不替代人工确认；技术通过不替代补丁接受或规则发布；无 holdout 仍 not_evaluated/draft。未绑定历史执行保留原 executor/checkpoint；`semflow` 为历史平台兼容命令，日常科研使用 `semflow-research`。

| 契约 | 当前版本 / 语义修订 |
| --- | --- |
| run / result | semflow.research.run/1.0（8）；semflow.research.result/1.0（4） |
| manifest / evidence / bundle | semflow.research.manifest/1.0（1）；semflow.research.evidence/1.0（2）；semflow.research.bundle/1（2） |
| approval / control / resources | approval（2）；control（1）；resources（2）；具体类型与 Schema 由 contracts/wire.py 声明 |
| OpenHands / corpus / rules | SDK 1.56.0；OpenHands policy/receipt（1）；corpus/1（2）；新 RuleResult 使用 semflow.rule-validation/2，旧 /1 不重解释 |

已交付入口适用于其明确冻结的方法/参数和兼容资源；implemented 不表示任意未知版本或参数组合均支持。discovery 编排方法 1；scout 方法 1～8、统一 review 4～12；repair generate 方法 3/4、build_suite 方法 2、verify 方法 1；RAG rules 方法 8。Prompt 版本单独冻结，不能用方法版本替代。

完整契约 ID、Schema 版本及语义修订以 `semflow-research capabilities` 和 `semflow-research schema` 为准；接口收发端注释继续要求同步检查对端，无新增 AGENTS.md 规则。方法版本和 Prompt 版本分别冻结。

| 后置任务 | 状态 | 未在本轮执行的内容 |
| --- | --- | --- |
| DEC-POST-001（关联 DEC-013） | planned | 历史算法副本/旧入口整理，保留可恢复历史 |
| DEC-POST-002（关联 DEC-012 运维部分） | planned | 实际实例部署、数据库迁移、切换与回退 |
| DEC-POST-003（关联 DEC-010） | planned | batch/消融、历史脚本迁移、真实模型效果及扩样 |
| DEC-POST-004 | planned | 全面 CI、wheel 构建/发行物与环境指纹整理 |

验收依据：[S5 矩阵](backend-decoupling-s5-matrix-20261113.md) 64 passed / 2 skipped；独立包既有回归 166 passed / 3 skipped；S6 能力、导入/桥接边界和 wire 轻量检查 **23 passed**，报告 `artifacts/decoupling/s6-boundary-check-20261113.xml`。模型/工具替身及真实工具小样本的范围按原证据保留。

工作区包含用户、既有实验和解耦改动，作者归属不能仅凭未提交状态推断；不改写这些历史、不提交产物。后置项只有用户明确要求才进入。
