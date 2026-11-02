# Backend

启动、数据库迁移与测试请参阅根目录 README.md。

API、调度、LangGraph、业务用例、CodeQL 适配器和持久化分别维护。Dockerfile 仅为应用镜像定义，本阶段验收使用本地 API 与 Worker；镜像不包含 CodeQL 或任务隔离执行器。

无 Web/任务队列的实验入口见 [实验 CLI 与共享内核](../../design/experiment-cli.md)。
从 `system/` 运行 `PYTHONPATH=backend .venv/bin/python -m app.cli --help`；
安装后可使用 `semflow run/batch/inspect/resume/retry/decide`。
