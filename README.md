# SemFlow Audit

围绕语义理解与数据流分析的代码审计平台，包含双引擎发现、证据复核、隔离修复验证和 RAG 规则生成四阶段链路。

## 仓库索引

| 主目录 | 内容 | 入口 |
| --- | --- | --- |
| `system/` | 项目系统源码、单元测试、脚本、运行配置和锁文件 | [系统与启动说明](system/README.md) |
| `benchmarks/` | 测试数据集、基准论文、测试方案和实验结果 | [测试资料索引](benchmarks/README.md) |
| `research/` | 代码审计方法论文、竞品论文、阅读笔记和书目 | [研究资料索引](research/README.md) |
| `design/` | 开发过程中的架构、模块边界、设计和实施计划 | [设计文档索引](design/README.md) |
| `competition/` | 竞赛作品报告、模板、测试章节、校对材料和配图 | [竞赛资料索引](competition/README.md) |

首次运行见[协作者环境与启动清单](system/collaborator-setup.md)。开发命令默认在 `system/` 执行；`.env` 与运行产物 `artifacts/` 保持在仓库根目录并由 Git 忽略。

当前系统已同步多页面 UI 工作台、AI 中文报告和项目级修复前后验证。新版 Windows 独立运行方式见 [UI 本地启动](system/LOCAL_SETUP.md)，页面与演示说明见 [工作台交付文档](design/UI_WORKBENCH_DELIVERY.md)。

## 归档说明

已登记 [46 项相关文献](research/papers/README.md)，已收集全文分布于 `research/papers/` 与 `benchmarks/papers/`；未下载项保留来源记录。[39 个测试数据包](benchmarks/datasets/README.md)包含 17,271 个成员，支持离线验证及恢复。

2026-10-12 完成五目录整理。[目录规则](design/repository-layout.md)说明归档边界；[迁移清单](design/repository-file-map.json)记录旧路径、新路径与原始 SHA-256。历史测试冻结记录保留原文，旧路径可通过清单查询；归档脚本兼容迁移前的收据路径。

测试方案、资料数量和历史结果分别记录；未完成、失败及未评估的实验状态不会因归档而改变。密钥、真实上传项目、审计产物及本地缓存不随仓库发布。论文、数据集和第三方源码遵循各自许可，项目许可见 [LICENSE](LICENSE)，编码约束见 [AGENTS.md](AGENTS.md)。
