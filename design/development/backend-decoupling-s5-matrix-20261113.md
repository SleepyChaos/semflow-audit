# S5 总验收矩阵（2026-11-13）

范围是四个当前科研切片的边界和双端可用性。执行 ID、时间和平台展示 DTO 允许不同；比较冻结输入语义、状态、错误和必要产物引用。

| 切片 | Core | 独立 CLI | Web 薄桥 | 契约/语义 | 必要失败与恢复证据 |
| --- | --- | --- | --- | --- | --- |
| Discovery | `public.discovery` 的 scan/scout/review/discover；双分支独立命名空间，Scout 不读静态结果 | `discovery-scan`、`discovery-scout`、`discovery-review`、`discovery-discover`，新进程无平台导入 | 上传扫描、双引擎、普通 Scout、统一 Review 经 `research_bridge` | run/result/bundle/evidence/coverage/derived_from/SARIF identity 保留，WIRE 注释成对 | SARIF 失败、Scout 失败、review partial、取消、重复投递、投影恢复；S4 专项 35 passed |
| Native repair | native repair graph、attempts、patch/source/check receipts | `repair-native` 自动装配上游目标、范围和确认 | repair binding 调用同一 public，投影旧 RepairRecord/Diff/validation | PatchScope、AttemptRecord、Failure.detail、静态基线引用 | 语义模型/验证失败、取消、重复投递、原源码不变；`test_research_native_process.py` 对照同一冻结请求 |
| OpenHands repair | OpenHands graph、固定 worker、预算/范围/取消收据 | `repair-openhands`，新进程无平台导入 | OpenHands binding 复用同一 worker/core | OpenHandsPolicy/Receipt、worker digest、usage 和失败收据 | worker 缺失/失败/取消/超时、重复投递；process/bridge 对照通过 |
| RAG rules | method 8 RAG、QL 编译/正反例、项目重放、holdout、typed resume/validate | `rule-generate`、`decide`、`resume`、`rule-validate` | approve-fixtures→resume 进入同一 core；现有 `confirm-project-match` 是平台人工项目匹配验收入口；publish 保持平台事务 | RuleResult、RuleDiagnostics、CorpusSnapshot、Approval/Control、验证语义 `/2` | 无 holdout draft/not_evaluated、过期 subject、资源/语料缺失、投影恢复；规则专项 172+ passed，等价验收测试通过 |

## 入口与平台边界

CLI 的 import guard、独立包回归和四个 discovery 命令证明 CLI 不导入 `app`、FastAPI、Celery、SQLModel、平台配置，也不调用 Web API。平台 bridge 负责冻结输入、ArtifactRef/平台 ID 转换、投影和人工/发布事务；当前算法仍在 research public/graphs/adapters 中。未绑定的历史 StageRun、旧 checkpoint 和 legacy executor 保留给历史恢复。

## 规则 Web 验收等价性

规则平台没有另造一个会重新生成规则的 `validate` 算法入口。现有产品路径是：

1. `approve-fixtures` 持久化精确 Approval/ControlCommand，并恢复原 checkpoint。
2. 同一规则 core 在生成阶段完成编译、开发 fixtures 与原项目重放；`research.public.rules.resume` 在批准后校验冻结工具链并执行批准 fixtures 与选定 holdout。投影保留各类技术收据，不重新生成规则。
3. `confirm-project-match` 只处理平台拥有的人工作品匹配确认，校验保存的 replay finding、目标确认和 baseline exclusion；它不重新执行科研验证。
4. `publish` 继续由平台检查 holdout、人工确认和平台状态。

因此该现有 Web 验收路径等价覆盖 `rules.validate` 的产品语义：科研技术验证由 core 完成，平台确认和发布由 Web 完成。`tests/test_research_rule_bridge.py::test_existing_project_match_route_is_the_platform_validation_acceptance_gate` 对此有实际证明。

## 收口证据

- S5 最小总矩阵：**64 passed / 2 skipped**，见 `artifacts/decoupling/s5-total-matrix-20261113-v2.xml`。
- 独立 contracts/research/CLI 回归：**166 passed / 3 skipped**，见 `artifacts/decoupling/s4-independent-regression-20261113.xml`。
- Discovery 四操作：**35 passed**，见 `artifacts/decoupling/s4-discovery-regression-20261113.xml`。
- 规则 CodeQL 小样本：CodeQL 2.23.5 + Python 3.11，见 `artifacts/decoupling/real-rule-cli-20261112-s3-v2/`。

本次解耦交付范围已完成。明确后置项仍保留在 TODO：历史算法清理、实际平台实例部署、batch/效果评测和全面 CI/wheel 整理；这些不改变新四切片的双入口边界。

S6 状态口径与后置清单统一见[一页交付摘要](backend-decoupling-delivery-20261113.md)。能力输出中 implemented 与 experimental 互斥；native/OpenHands 及规则 method 8 属于已交付范围。
