# 后端解耦 PR 交付记录（2026-11-15）

本 PR 整理三个科研内核、独立 CLI、平台桥接及必要兼容依赖。基于远程 main 的 `52d8fa2`，保留已合并的 Windows/Docker 多阶段部署配置。用户要求本次整理提交，后续测试发现的问题只记录、不修复。

## 代码边界

- `system/contracts`：运行输入、证据、产物、批准、控制与资源等类型及 JSON Schema。语义约束保留在对应接口声明和发送/接收注释中；本 PR 不修改 AGENTS.md。
- `system/research`：双引擎漏洞发现与统一复核、native/OpenHands 修复与测试集/前后验证、RAG QL 生成与批准恢复、独立验证。显式冻结源码、方法/Prompt、模型策略、工具链和语料。
- `system/research_cli`：直接调用 research public 的独立命令；不加载平台 app、数据库、队列或 .env。
- `system/backend/app/research_bridge`：冻结平台输入、ID/引用转换、结果投影及人工事务。新执行调用同一 public；未绑定历史执行保留原算法及检查点。
- 平台 application/runtime/presentation 分离任务调度、事务后续任务与展示；包含 `c1d202611100`、`c2d202611110` 两个迁移。合并源码不等于部署，未对实际实例执行迁移。
- 包含科研内核抽取所需的既有 OpenHands、旧平台 CLI 和兼容执行组件；未纳入独立的基准实验脚本改进、实验记录、真实项目归档、产物、密钥或本地运行配置。

## 既有运行证据及限制

完整过程见[操作验收清单](backend-decoupling-acceptance-checklist-20261113.md)。本地证据运行 ID 为 `20261113T133759-26ecb8`；产物留在忽略目录 `artifacts/decoupling/`，不作为源码提交。

- 仓库外 wheel CLI 与实际 GUI/HTTP/Celery 已完成固定合成样本流程。CodeQL、Docker 和 OpenHands SDK 为真实工具，确定性对照中的模型为显式 HTTP 替身。
- CLI/Web 55 项对照中 53 项原始相等，另两项为契约定义的等价 readable_paths 编码，无未解释差异。
- 真实模型 discovery 成功；合成样本 native 在两次调用后预算耗尽，RAG 两次请求超时，保留失败收据。
- RealVuln 仅选择 Damn Vulnerable Flask Application，commit `55f63201c85190e760a8fa34a580a9bf918dbf36`，真实 CodeQL 命中 `app.py:120`，真实模型 scout 为 partial、review 为 supported。未完成该真实项目的修复和规则链路，不能声称三内核真实项目端到端全部通过。
- GUI 运行中取消缺少有效现场收据（点击时任务已结束，ACC-007 blocked）。规则样本与原基线同根，发布门保持阻断；未编造排除理由。ACC-010 仍待监督复核。
- 旧归档对照已运行发现/native/suite/verify；归档缺少旧前端和 OpenHands worker，不构成完整旧 GUI/OpenHands 重现。

## 本次提交检查

在独立工作树检查最终提交内容，避免依赖原工作区未提交文件。Ruff（平台、三个独立包及独立包测试）、锁文件离线校验、修改页面的 Biome、仓库内部导入目标检查和凭据形态扫描通过。

本地 Docker daemon 未运行，未启动实际平台服务。数据库回归由 PR 中既有隔离 PostgreSQL CI 执行；本地独立包/SQLite 桥接回归 **183 passed / 4 deselected**（排除 integration；JUnit 为 `/private/tmp/semflow-decoupling-pr-tests-20261115.xml`），GitHub CI 状态记录于 PR。不得用历史测试数或 implemented 字段代替本次未完成的运行验收。
