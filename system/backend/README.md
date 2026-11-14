# Backend

启动、数据库迁移与测试请参阅根目录 README.md。

API、调度、LangGraph、业务用例、CodeQL 适配器和持久化分别维护。Dockerfile 仅为应用镜像定义，本阶段验收使用本地 API 与 Worker；镜像不包含 CodeQL 或任务隔离执行器。

历史平台兼容命令见[旧 CLI 说明](../../design/experiment-cli.md)；独立科研入口见[科研 CLI](../research_cli/README.md)。
从 `system/` 运行 `PYTHONPATH=backend .venv/bin/python -m app.cli --help`；
安装后可使用 `semflow run/batch/inspect/resume/retry/decide`。

上述 `semflow` 是依赖平台数据库的 legacy 入口；新的[独立科研 CLI](../research_cli/README.md)
已交付 discovery、native/OpenHands repair 和 method 8 rules 的独立科研执行入口。平台的新科研任务经 research_bridge 调用同一 public core，未绑定历史任务保留旧执行器；旧命令不作为日常科研入口。交付版本和后置范围见[摘要](../../design/development/backend-decoupling-delivery-20261113.md)。

修复完成后的自动前后验证已迁到平台应用层。更新代码前后请按既有流程执行 `alembic upgrade head`，
新增迁移 `c1d202611100` 建立 `stage_followup` 表；未对既有平台实例自动执行迁移。
修复完成与后续意图同事务提交，算法图不直接投递队列。平台 runtime 处理正常投递；
崩溃留下的 pending / 过期租约可由独立 Celery beat 每 60 秒补偿，或在 backend 目录手动运行：

```sh
../.venv/bin/python -m app.application.repair_followups
```

需要持续补偿时另外启动 `celery -A app.jobs.celery_app:celery_app beat`。
投递失败保留独立 verification 失败记录和原补丁；failed 意图不自动创建新执行，继续使用明确的新建重试。
