# Docker 启动

在仓库根目录运行（Windows PowerShell、macOS/Linux 均可）：

```sh
python system/scripts/init_local.py
docker compose up -d --build --wait
```

首次构建需要访问 Docker Hub、GHCR、PyPI 和 npm。主机无需安装项目的 Python 3.14、Node 或前后端依赖；第一条命令只需已有 Python，用于生成本地随机密码，不覆盖现有 `.env`。

- 工作台：http://localhost:5174
- API 文档：http://localhost:8001/docs
- 状态：`docker compose ps -a`
- 日志：`docker compose logs --tail 100 backend worker init`
- 停止并保留数据：`docker compose down`
- 更新代码后重新构建：`docker compose up -d --build --wait`

Compose 启动 PostgreSQL、Redis、一次性数据库初始化、API、Celery Worker 和 Nginx 前端。`init` 成功退出是正常状态；它自动执行 Alembic、工作区初始化与 LangGraph 检查点建表。前端同源代理 `/api/`，支持深层路由刷新。各宿主机端口仅绑定本地回环地址。

根目录 Compose 与 `system/compose.yml` 的数据库模式使用不同项目名；两者默认使用相同数据库端口，请勿同时运行。现有纯主机启动流程仍可使用 `system/compose.yml`。

## 本地配置和持久化

数据库、Redis 和 Linux 扫描运行时使用命名卷；上传代码和审计结果位于根目录 `artifacts/`，API 与 Worker 共享同一目录。`.env` 不进入镜像。Compose 会覆盖其中仅适用于主机的数据库、Redis 和产物地址。可以在 `.env` 中设置 `UI_FRONTEND_PORT`、`UI_API_PORT`、`UI_DB_PORT`、`UI_REDIS_PORT` 来调整默认端口。

AI 阶段需要在 `.env` 配置 `AI_BASE_URL`、`AI_MODEL`、`AI_API_KEY`。变更后运行 `docker compose up -d --force-recreate backend worker`。没有模型配置仍可浏览工作台、上传和管理任务；AI 阶段不能完成。

## CodeQL 和修复验证的边界

基础镜像不包含 CodeQL、Python 3.11 抽取运行时或嵌套 Docker。环境检查会如实报告缺少扫描工具；不能把页面可访问视为完整审计链路已通过。

在 Windows 上使用 Docker Desktop 的 **WSL2 / Linux amd64 容器**。不要把 Linux 运行时直接解压到 NTFS：部分 Python 工具文件仅大小写不同，会发生冲突。可选工具准备服务会从官方来源下载并校验 SHA-256，把 CodeQL 2.23.5、Python 3.11.14 安装到大小写敏感的 Docker 命名卷，并准备固定查询包和查询源码：

```sh
docker compose --profile tools run --rm --build tools
docker compose up -d --wait
```

工具准备服务不加载 `.env` 或模型凭据。API/Worker 只读挂载运行时，查询包保存在 `artifacts/packs/`。官方安装包缓存在 `.tools/downloads/`，已有文件需通过固定哈希校验才会复用。若下载中断可重新运行；网络受限时，可从 `docker_tools.py` 指定的官方地址下载同名文件到缓存目录后再运行。Windows 的 `codeql.exe` 不能在 Linux 容器内执行。

这两个命名卷用于 Linux amd64；ARM 主机、Windows 原生容器和其他版本组合未在本次验证范围内。工具准备遵循 CodeQL 的许可条件。

当前修复验证器直接调用 Docker CLI 并使用绝对路径创建同级容器；基础 Compose 没有挂载主机 Docker socket，因此尚不能执行隔离修复验证。要启用该链路，需要额外处理 Docker CLI/引擎访问和宿主机产物路径映射。可先使用原有主机 Worker 方式执行该功能。规则生成还需要独立准备知识材料和索引。

## 镜像目标

`system/backend/Dockerfile` 提供 `backend`、`frontend`、`standalone` 三个目标。根目录 Compose 使用前两个；单独 `docker build -f backend/Dockerfile .` 仍输出包含静态前端的完整 API 镜像。

## 最小真实流程测试

准备好扫描工具和模型配置后，在 Windows PowerShell 或其他主机终端运行：

```sh
python system/scripts/docker_smoke.py --output artifacts/local/docker-smoke.json
```

测试使用自动生成的小型 Flask 代码包，不会启动其中的示例服务。代码包含一个预期的注入问题，用于验证固定 CodeQL 规则；ZIP 文件名和路径包含中文及空格，源码使用 CRLF 换行。

脚本通过 Nginx 同源 API 上传，等待真实 CodeQL 和 AI 初审完成，验证源码预览、SARIF 下载、模型实际调用，以及预期的 `py/code-injection` 告警。所有检查通过才返回退出码 0；缺少依赖、分支失败或超时均返回非零值。每次会保留一条明确标注为 smoke 的合成任务，JSON 结果不包含密钥。这是兼容性流程检查，不评估模型审计准确率或完整修复/规则发布链路。
