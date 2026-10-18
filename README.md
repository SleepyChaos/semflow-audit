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
| `TODO/` | 待办、交互问题及流程讨论记录 | [前端问题与流程表](TODO/frontend-issues-and-flow.md) |

跨平台协作从根目录 [Docker 启动说明](DOCKER.md) 开始，包含 Windows PowerShell 和 macOS/Linux 启动步骤及当前支持范围；容器实现和实测记录见 [system/docker/README.md](system/docker/README.md)。原生开发见[协作者环境与启动清单](system/collaborator-setup.md)。开发命令默认在 `system/` 执行；`.env`、`.env.docker` 与运行产物 `artifacts/` 保持在仓库根目录并由 Git 忽略。

当前系统已同步多页面 UI 工作台、AI 中文报告和项目级修复前后验证。新版 Windows 独立运行方式见 [UI 本地启动](system/LOCAL_SETUP.md)，页面与演示说明见 [工作台交付文档](design/UI_WORKBENCH_DELIVERY.md)。

## 启动与开发文档

| 文档 | 用途 |
| --- | --- |
| [DOCKER.md](DOCKER.md) | 协作者 Docker 首次启动、模型配置、更新、停止与排障 |
| [system/docker/README.md](system/docker/README.md) | 容器实现、固定版本、初始化及实际验证范围 |
| [system/README.md](system/README.md) | 系统开发总入口与原生启动命令 |
| [协作者环境清单](system/collaborator-setup.md) | 原生开发的依赖、端口及环境变量 |
| [Windows 原生启动](system/LOCAL_SETUP.md) | 保留的 Windows 独立副本启动方式 |
| [脚本导航](system/scripts/README.md) | 初始化、知识采集、实验与归档脚本入口 |
| [AGENTS.md](AGENTS.md) | 项目编码、模块边界与证据校验约束 |

阅读系统设计从 [design/README.md](design/README.md) 开始；查实测结论从 [benchmarks/README.md](benchmarks/README.md) 开始；查论文和阅读笔记从 [research/README.md](research/README.md) 开始。`TODO/` 是待办记录，完成状态以实现和实测记录为准；`artifacts/` 是本地运行数据，不属于共享文档。

## 归档说明

已登记 [46 项相关文献](research/papers/README.md)，已收集全文分布于 `research/papers/` 与 `benchmarks/papers/`；未下载项保留来源记录。[39 个测试数据包](benchmarks/datasets/README.md)包含 17,271 个成员，支持离线验证及恢复。

2026-10-12 完成五目录整理。[目录规则](design/repository-layout.md)说明归档边界；[迁移清单](design/repository-file-map.json)记录旧路径、新路径与原始 SHA-256。历史测试冻结记录保留原文，旧路径可通过清单查询；归档脚本兼容迁移前的收据路径。

测试方案、资料数量和历史结果分别记录；未完成、失败及未评估的实验状态不会因归档而改变。密钥、真实上传项目、审计产物及本地缓存不随仓库发布。论文、数据集和第三方源码遵循各自许可，项目许可见 [LICENSE](LICENSE)，编码约束见 [AGENTS.md](AGENTS.md)。
