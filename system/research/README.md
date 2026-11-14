# SemFlow research

`semflow-research` 独立于 app、FastAPI、Celery、SQLModel 和平台配置。CLI 与 Web 桥接调用相同的 `public`；三内核的本次解耦交付范围已完成；历史清理、效果评测和实际平台部署仍是后置事项。

已交付入口（CLI/Web 解耦边界）：

- discovery：scan / scout / review / discover。包括独立的 CodeQL 与 Scout 分支、统一复核、冻结补充规则、真实数据库/SARIF 的交接；模型意见和人工决策分开。
- repair：native / OpenHands generate、build_suite / verify，支持冻结 StaticBaseline 复扫、项目测试与独立 before/after。保留逐次尝试、实际源码、范围与检查收据；技术通过不代表人工接受。
- rules：method 8 的 RAG 生成、冻结语料、编译/开发图、typed 样例批准暂停及原检查点续接；无 holdout 明确保持 draft/not_evaluated。项目重放、完整 Web 投影/发布门和独立 `rules.validate` 已接通；独立复核只接收批准生成清单，不读取生成工作区或重新生成。

Web 新建扫描、普通 Scout、统一复核和 native / OpenHands 修复验证任务经 `app/research_bridge` 调用这里；平台负责身份、归属、人工确认、调度与旧视图。历史未绑定任务保留原执行器，不转换其 checkpoint。新 OpenHands 使用同一科研实现，资源缺失明确失败；规则平台桥接、发现双端对照和新入口归一已完成；历史未绑定任务继续使用 legacy executor。

OpenHands 由独立固定 SDK 解释器和任务专属禁网容器执行。输入冻结 Prompt、镜像 digest、模型 endpoint、执行/停滞时限与预算，资源快照还绑定实际复制的 worker 文件摘要；源码可读/可写范围、已观察窗口和文件数上限都由科研内核检查。每次 SDK 模型调用使用与语义模型相同的持久预算账本，未知结果保留占用。成功、失败、超时和取消均保留 `OpenHandsReceipt`，包含日志、事件、原始 runtime 结果及部分工作区的不可变引用；完整检查和人工接受保持独立。

`discovery / repair / rules / graphs` 拥有算法；`adapters` 接入模型、CodeQL、执行器与检索；`runtime` 只装配显式依赖、验证输入产物并持久化科研执行；`state` 不含平台用户/工作区/阶段表。产物位于独立 root 下，科研执行 ID 与平台 ID 不相同。

关键 JSON 在类型声明、Schema 与发送/接收接口注释中说明语义和对端，Agent 修改时需同时检查两端与兼容测试；没有新增 AGENTS.md 规则。诊断 trace 供平台转换旧展示数据，科学结论仍以类型化集合和收据为准。旧收据按原保存 JSON 校验，不因新增可选默认值重算历史摘要；使用变化后的请求/实现继续执行需新尝试或原冻结版本。

三个 wheel 和完整锁定运行依赖闭包已在空环境离线安装验证；不使用 system-site-packages，也不安装平台包。验证依赖按 uv.lock 的 Python 条件分支选择，并校验发行包 RECORD。该门不代表真实模型效果或完整科研方法验收。

```sh
# 在 system/ 下
.venv/bin/pytest contracts/tests research/tests research_cli/tests -q
uv lock --check --offline
```

入口、契约版本、验收范围与后置清单见[交付摘要](../../design/development/backend-decoupling-delivery-20261113.md)；[主 TODO](../../design/development/backend-decoupling-todo-20261110.md) 保留逐阶段历史。capabilities 中 implemented 与 experimental 不重叠，repair 的 implemented_engines 为 native/openhands，rules 的 implemented_methods 为 8。
