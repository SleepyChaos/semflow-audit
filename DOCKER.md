# Docker 启动说明

本说明用于 Windows、macOS、Linux 协作者启动 SemFlow Audit。所有命令都在包含本文件和 `system/compose.full.yml` 的仓库根目录执行。

## 当前支持范围

Docker 应用栈包含生产前端、FastAPI、Celery Worker、PostgreSQL/pgvector、Redis、CodeQL 及 Python/JavaScript 固定查询库，首次启动会初始化数据库和 RAG 基础材料。宿主机不需要另外安装 Python、Node、uv 或 CodeQL；RAG 默认使用 BM25，不需要向量化服务。

原有本机启动方式仍然保留。修复验收使用独立的 Docker-in-Docker 服务 `validator`，通过 TLS 连接，不挂载宿主机 Docker socket，也不暴露 Docker 控制端口。该服务需要 `privileged` 权限；不要在不可信的共享宿主环境部署。

`validator-init` 会构建 Python/Flask 测试镜像并准备 Node 镜像，成功后才启动 API 和 Worker。测试容器禁止联网、源码只读、非 root 运行，并限制 CPU、内存与进程数。内置 Flask 环境覆盖本仓库 RealVuln Flask 演示；其他项目依赖仍需专用镜像，不会自动安装上传项目声明的任意依赖。

2026-10-18 已在 macOS Docker Desktop 上验证镜像构建、服务健康、页面访问、六个基础规则示例编译及真实 CodeQL 样例扫描。容器内完整 AI 复审/报告流程、Windows 真机启动尚未验收。

## 1. 准备 Docker

- Windows/macOS：安装并启动 Docker Desktop；Windows 使用 WSL2 后端和 Linux containers。
- Linux：安装 Docker Engine 和 Docker Compose 插件，确保当前终端可以运行 Docker。
- 建议分配至少 4 个 CPU、8 GB 内存和 20 GB 可用空间。
- Apple Silicon 的应用容器使用 `linux/amd64` 仿真，首次构建和扫描可能较慢。

终端执行以下命令，确认 Docker 服务和 Compose 可用：

```sh
docker info
docker compose version
```

## 2. 首次生成配置

Windows PowerShell：

```powershell
powershell -NoProfile -File system/docker/start.ps1 up
```

macOS / Linux：

```sh
sh system/docker/start.sh up
```

没有 `.env.docker` 时，脚本会生成该文件及随机数据库密码，然后以退出码 **2** 停下，提示填写模型密钥。这是首次配置提示。已有文件会保留；若已经配置完成，脚本会直接构建并启动服务。

编辑根目录 `.env.docker`，核对以下项目：

| 配置项 | 填写方式 |
| --- | --- |
| `POSTGRES_PASSWORD` | 保留自动生成的密码 |
| `APP_PORT` | 默认 `5181`；被占用时修改 |
| `AI_BASE_URL` | 模板默认 `https://ark.cn-beijing.volces.com/api/coding/v3` |
| `AI_MODEL` | 模板默认 `deepseek-v4.1-flash`，需确认密钥有访问权限 |
| `AI_API_KEY` | 填写模型服务密钥；不要提交到 Git |
| `IMAGE_REGISTRY` | 默认 `docker.io`；镜像代理故障时见下方排障说明 |

Docker 使用独立的 `.env.docker`，原生开发使用的 `.env` 不会被覆盖。数据库、Redis 和工具路径由 Compose 配置，不要填写协作者电脑上的绝对路径。

## 3. 构建并启动

保存配置后，再运行上一步对应平台的 `up` 命令。也可以直接运行三平台通用命令：

```sh
docker compose --env-file .env.docker -f system/compose.full.yml up -d --build --wait --wait-timeout 1800
```

首次构建会下载镜像、CodeQL 和锁定依赖，并编译基础规则；需要能够访问 Docker Registry、GitHub 和依赖源。初始化成功后才启动 API 和 Worker。

启动成功后打开 **<http://localhost:5181>**；修改过 `APP_PORT` 时使用对应端口。前端与 API 同源，无需再启动 Vite。这个地址仅绑定本机。

## 4. 查看状态与日志

```sh
docker compose --env-file .env.docker -f system/compose.full.yml ps -a
docker compose --env-file .env.docker -f system/compose.full.yml logs --tail 100 init validator validator-init api worker
```

正常状态：`db`、`redis`、`validator`、`api`、`worker` 为 `healthy`，一次性初始化服务 `init` 与 `validator-init` 为 `Exited (0)`。

浏览器也可打开 [扫描环境接口](http://localhost:5181/api/v1/audits/environment)，查看 CodeQL 版本、查询包和队列状态；自定义端口时同步修改地址。

启动脚本也提供 `doctor`、`logs`、`down`，将命令末尾的 `up` 替换为对应操作即可。

## 5. 更新与停止

确认当前后台任务结束后，更新代码并重新运行 `up`，使 API 与 Worker 使用同一版本镜像。

停止服务并保留数据：

```sh
docker compose --env-file .env.docker -f system/compose.full.yml down
```

数据库、队列和审计产物保存在 `semflow-container` 项目的命名数据卷中。**不要追加 `-v`，它会删除数据卷。** 新容器工作空间不会自动导入原生开发中的任务、源码包、规则或审计历史；会初始化自己的基础 RAG 材料。数据库卷创建后，单独修改配置文件中的密码不会自动修改数据库用户密码。

## 常见启动问题

| 现象 | 处理方式 |
| --- | --- |
| 找不到 Docker、无法连接守护进程 | 安装或启动 Docker Desktop；Linux 检查 Docker 服务和当前用户访问权限 |
| 提示必须使用 Linux containers | 在 Docker Desktop 切换到 Linux 容器；Windows 检查 WSL2 后端 |
| 首次运行退出码为 2 | 编辑新生成的 `.env.docker`，填入模型密钥，再运行 `up` |
| PowerShell 策略禁止运行脚本 | 使用第 3 节的通用 Compose 命令；配置文件可从 `system/docker/compose.env.example` 手动复制，填写随机字母数字数据库密码和模型密钥 |
| 5181 端口被占用 | 修改 `.env.docker` 中的 `APP_PORT`，重新运行 `up` |
| `load metadata`、代理 `502` 或 Registry 超时 | 检查 Docker Desktop 的代理、DNS 和镜像源；本地镜像代理故障时可设置 `IMAGE_REGISTRY=registry-1.docker.io` 后重新构建，仍使用官方仓库及固定摘要 |
| API/Worker 没有启动，`init` 非零退出 | 先查看 `init` 日志，修复迁移或基础材料初始化错误；不要删除数据卷来掩盖错误 |
| 页面可打开，但 AI 阶段失败 | 核对模型地址、密钥和模型权限；修改后重新运行 `up` |
| 前后对比提示验证环境不可用 | 查看 `validator`、`validator-init` 日志；确认未禁止 privileged 容器、TLS 证书卷存在、测试镜像初始化成功。页面恢复后可重跑，无需重建补丁 |

## 相关文档

- [项目文档总入口](README.md)：目录结构和各类文档用途。
- [容器实现与验证记录](system/docker/README.md)：固定工具版本、初始化细节及当前验证边界。
- [系统开发说明](system/README.md)：系统源码及原生开发命令。
- [协作者原生环境清单](system/collaborator-setup.md)：不使用应用容器时的工具与配置。
- [架构与设计文档](design/README.md)：模块边界、审计流程和验收要求。
