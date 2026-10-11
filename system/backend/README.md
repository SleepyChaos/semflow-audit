# Backend

启动、数据库迁移与测试请参阅根目录 README.md。

API、调度、LangGraph、业务用例、CodeQL 适配器和持久化分别维护。Dockerfile 仅为应用镜像定义，本阶段验收使用本地 API 与 Worker；镜像不包含 CodeQL 或任务隔离执行器。
