# SemFlow Audit 工作区迁移

日期：2026-10-09。迁移目的：将当前开发代码和研究工作统一放入本机 GitHub 目录，并以新的私人仓库继续维护。

## 名称与位置

- 名称：**SemFlow Audit**；Semantic Flow，表示语义理解与数据流分析。
- 本地项目：`/Users/chaos/Documents/GitHub/semflow-audit/`
- 新私人仓库：`https://github.com/SleepyChaos/semflow-audit`
- 旧远程：`https://github.com/SleepyChaos/ai-code-audit.git`，作为历史来源保留。

## 已迁移的内容

- 后端、前端、测试、脚本与锁定依赖清单。
- `docs/` 中的设计、研究、基准结果和 LLM/CodeQL 协同方案。
- `benchmark-data/` 中的材料、索引、实验计划与续接状态。
- 本地 `.env`、虚拟环境、前端依赖及 `artifacts/` 的运行/审计产物。
- 原会话 `work/` 与 `outputs/` 移入 `.local-workspace/work/`、`.local-workspace/outputs/`。

采用同文件系统目录重命名，保留目录身份与完整内容；迁移收据保存在 `.local-workspace/migration-receipt.json`。旧项目及 `work/outputs` 路径保留符号链接，使既有绝对路径、虚拟环境入口和报告引用可继续访问。

现有 Docker 容器归属 Compose 项目 `ai-code-audit`。已在仅本地的 `.env` 中固定 `COMPOSE_PROJECT_NAME=ai-code-audit`，并通过配置解析核对，迁移后继续使用原数据库与 Redis 数据卷。没有重启服务或新建数据库。

## GitHub 提交范围

保留已有 Git 历史，并提交本轮迁移前的最新代码、研究文档和可提交实验索引。项目既有忽略规则继续排除密钥、虚拟环境、node_modules、原始数据、论文副本、评测答案、模型输入与审计产物；新增忽略 `.local-workspace/`。

这些排除项已经迁入新本地目录。它们的体积和再分发边界不适合直接放入 Git；远程复现依靠脚本、索引与固定版本记录。迁移没有重新执行 GUI、模型或漏洞能力实验。

本轮迁移前核查 627 个可提交文件，约 4.96 MB；可提交内容和当前分支可达历史的 469 个 blob 未发现所检查的常见凭据格式。模式扫描不是对所有形式的密钥泄露作完整保证。

## 继续工作的入口

- 研究候选：[LLM 与 CodeQL 协同方案](../research/notes/codeql-llm-proposals-index.md)。
- 实验恢复：[状态](../benchmarks/experiments/state.json)与[日志](../benchmarks/experiments/journal.md)。
- 中段介入方案仍为设计候选；本次迁移不改变既有结果口径或自动启动新实验。
