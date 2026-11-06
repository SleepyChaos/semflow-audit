# SemFlow Audit

围绕语义理解与数据流分析的代码审计平台，包含双引擎发现、证据复核、隔离修复验证和 RAG 规则生成四阶段链路。

## 当前状态

**可信本地代码的研究原型，当前 CodeQL 扫描覆盖 Python 与 JavaScript/TypeScript。** 项目用于研究模型与静态分析如何协作发现、复核和修复缺陷；模型判断、规则复扫和测试通过都不等于业务正确性或安全性证明。

| 阶段 | 主要工作 | 需要人工参与的边界 |
| --- | --- | --- |
| 发现 | 对同一源码快照运行 CodeQL 与独立 Agent 粗筛 | 粗筛可能仅覆盖部分源码，候选需复核 |
| 复核 | 基于源码取证，保留支持、排除及未决结果 | 模型建议与人工确认分开保存 |
| 修复 | 生成候选 Diff，在隔离验证环境中测试和复扫 | 人工决定是否接受修复 |
| 规则生成 | 检索资料、生成 CodeQL 规则、编译与正反例验证 | 规则需独立验收和批准发布 |

API/Worker 使用 Python 3.14、FastAPI、LangGraph 和 Celery；前端使用 React、TypeScript 与 Vite，数据层使用 PostgreSQL/pgvector 与 Redis。API Python 与 CodeQL 抽取用 Python 3.11 分开准备，具体版本以锁文件及[环境清单](system/collaborator-setup.md)为准。

## Docker 一键启动

前端、API、Worker、PostgreSQL 和 Redis 可在仓库根目录通过 Docker Compose 启动，自动初始化数据库。启动命令、端口和完整审计依赖的边界见 [Docker 启动说明](DOCKER.md)。

## 从哪里开始

- **第一次运行**：按[协作者环境与启动清单](system/collaborator-setup.md)准备 Docker、CodeQL、依赖、数据库和 API/Worker/前端三个进程。Windows 独立启动方式见 [UI 本地启动](system/LOCAL_SETUP.md)。
- **了解能力与限制**：读[系统说明](system/README.md)，再看[工作台说明](design/UI_WORKBENCH_DELIVERY.md)。没有模型配置时可进入界面，但无法完成 AI 阶段；完整规则链路还需要知识材料与索引。
- **查看实验依据**：从[实验索引](benchmarks/experiments/README.md)选择具体协议和对应结果。流程测试、真实工具集成测试与模型效果实验分别记录，不互相替代。
- **修改系统**：从 `system/` 下对应模块开始，先读[架构边界](design/architecture.md)和[编码约束](AGENTS.md)。

当前 CodeQL 扫描仍在主机执行，修复验证使用 Docker；本地工作台不提供账号登录。该运行方式不适合作为直接接收不可信上传的公共审计服务。

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

## 研究资料与实验记录

已登记 [46 项相关文献](research/papers/README.md)，已收集全文分布于 `research/papers/` 与 `benchmarks/papers/`；未下载项保留来源记录。[39 个测试数据包](benchmarks/datasets/README.md)包含 17,271 个成员，支持离线验证及恢复。

2026-10-12 完成五目录整理。[目录规则](design/repository-layout.md)说明归档边界；[迁移清单](design/repository-file-map.json)记录旧路径、新路径与原始 SHA-256。历史测试冻结记录保留原文，旧路径可通过清单查询；归档脚本兼容迁移前的收据路径。

测试方案、资料数量和历史结果分别记录；未完成、失败及未评估的实验状态不会因归档而改变。密钥、真实上传项目、审计产物及本地缓存不随仓库发布。论文、数据集和第三方源码遵循各自许可，项目许可见 [LICENSE](LICENSE)，编码约束见 [AGENTS.md](AGENTS.md)。

## 来源与许可

应用基础复用了 [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)；固定提交与复用范围见[模板来源](design/upstream.md)。原许可文本见 [LICENSE](LICENSE)。论文全文、基准数据、第三方源码与模型服务分别遵循其来源条件，根目录许可不替代这些资源的许可。
