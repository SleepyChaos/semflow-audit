# 容器化协作环境

协作者首次启动见仓库根目录 [Docker 启动说明](../../DOCKER.md)；本页保留容器实现细节和实测记录。

应用栈已在 macOS Docker Desktop 上完成真实构建、启动和 CodeQL 样例扫描。独立修复验证服务尚待批准，完整四阶段尚未验收。现有 `system/compose.yml` 与本机开发服务保留。

目标是 Windows、macOS、Linux 使用同一 Linux 工具链：生产前端、FastAPI、Celery、PostgreSQL/pgvector、Redis、CodeQL CLI 2.23.5、固定 Python/JavaScript 查询库和 RAG 初始化。协作者不需要安装 uv、Python、Node 或 CodeQL。

## 准备

安装 Docker Desktop，切换到 Linux containers；Windows 使用 WSL2 后端。建议为 Docker 分配至少 8 GB 内存、4 个 CPU 和 20 GB 空间。Apple Silicon 使用 `linux/amd64` 仿真以匹配该版本 CodeQL，扫描速度可能较慢。CodeQL 使用须符合其许可。

在仓库根目录运行启动脚本，自动创建随机数据库密码，然后编辑生成的 `.env.docker` 加入模型密钥并再次运行。脚本按自身位置定位项目，支持包含空格的路径，宿主机无需 Python/Node。Windows PowerShell 5.1/7：

```powershell
powershell -NoProfile -File system/docker/start.ps1 up
powershell -NoProfile -File system/docker/start.ps1 doctor
```

macOS / Linux：

```sh
sh system/docker/start.sh up
sh system/docker/start.sh doctor
```

首次创建配置后脚本以退出码 2 提醒填写密钥。已有配置不会覆盖，`down` 保留数据卷，`logs` 显示初始化和应用日志。若 PowerShell 的组织策略禁止本地脚本，使用下方原生 Docker Compose 命令即可，无需修改系统执行策略。

若需手动配置，复制下面的模板；已有配置不要覆盖。macOS / Linux：

```sh
cp system/docker/compose.env.example .env.docker
```

Windows PowerShell：

```powershell
Copy-Item system/docker/compose.env.example .env.docker
```

编辑 `.env.docker`，填写随机 `POSTGRES_PASSWORD`、`AI_API_KEY` 和模型服务配置。数据库密码建议使用 32 位以上字母数字，避免 URL 特殊字符。这里使用单独配置文件，原本机 `.env` 不受影响。不要提交配置文件或密钥。

## 构建与启动

以下命令在三种平台都从仓库根目录运行：

```sh
docker compose --env-file .env.docker -f system/compose.full.yml up -d --build --wait --wait-timeout 1800
```

访问 <http://localhost:5181>；端口可由 `APP_PORT` 修改。静态页面和 API 同源，不依赖开发服务器代理。

首次构建需要访问 Docker Registry、GitHub CodeQL 发行物/包仓库和依赖源。CodeQL 压缩包会核对固定 SHA-256。初始化按数据库健康、迁移、工作空间、LangGraph 检查点、RAG 材料的顺序运行，失败时不会提前启动 API/Worker。基础材料取自已安装固定查询库，包含两种语言的代码注入、SQL 注入、反射 XSS；范例标为真实编译验证，未冒充独立准确率测试。默认 BM25，不需要向量服务。不会自动上传源码或调用模型。

Node、Python 基础镜像固定到官方 amd64 摘要，uv 固定版本由 Python 依赖源安装，减少额外镜像仓库依赖。文本文件统一 LF，避免 Windows checkout 改变容器脚本、Prompt 或源码的换行。镜像内不复制宿主 `.venv`、`node_modules` 或已有构建产物。

查看状态和错误：

```sh
docker compose --env-file .env.docker -f system/compose.full.yml ps -a
docker compose --env-file .env.docker -f system/compose.full.yml logs --tail 100 init api worker
```

如果构建停在 `load metadata`，或错误中出现镜像代理域名、`502 Bad Gateway`、`context deadline exceeded`，失败发生在基础镜像下载阶段。检查 Docker Desktop 的代理、DNS 和 registry mirror 可达性后再重试；无需重建数据库或删除数据卷。不要用宿主机恰好缓存的不同版本镜像冒充锁定版本。

如果只有本地镜像代理失败，在 `.env.docker` 中设置 `IMAGE_REGISTRY=registry-1.docker.io`，再重新构建应用镜像。这仍使用官方仓库和相同 SHA-256，不修改 Docker Desktop 全局设置。数据库/Redis 若也需要重新下载，仍需保证其仓库可达。

启动成功后检查环境：

```sh
docker compose --env-file .env.docker -f system/compose.full.yml exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/audits/environment').read().decode())"
```

更新代码后重新运行构建启动命令；API 与 Worker 使用同一镜像，避免只有 API 更新而 Worker 仍加载旧代码。存在任务时先等任务结束再更新。

## 数据与当前边界

数据库、队列、审计产物使用命名数据卷，不引用 macOS/Windows 宿主路径，也不自动迁移原预览中的上传项目和历史记录。停止使用 `down`，不要加 `-v`，否则会删除数据库和审计数据。数据库卷初始化后修改密码不会自动更改已有 PostgreSQL 用户密码。

```sh
docker compose --env-file .env.docker -f system/compose.full.yml down
```

当前配置没有挂载宿主机 Docker socket，也没有部署高权限 Docker 守护进程。因此扫描、复审、报告和规则所需环境可在应用镜像中准备；修复阶段的隔离测试/前后对比尚不可在这份应用栈中执行，需要完成独立验证服务接入后才算完整容器化。Windows 真机验证尚未进行，不以 macOS 上容器成功代替 Windows 验收。

2026-10-18 验证记录（macOS Docker Desktop，应用容器为 linux/amd64）：

- 固定版本镜像构建、前端 TypeScript/Vite 生产构建通过。首次遇到本地镜像代理 `502` 后，使用官方 Registry 配置完成构建。
- 全新数据库迁移、工作空间、LangGraph 和 RAG 初始化通过；六个 Python/JavaScript 官方规则示例完成真实编译并写入双集合。
- API、Worker、PostgreSQL 和 Redis 健康检查通过；首页、前端资源、带 HTML 请求头的深层链接刷新及环境接口正常。
- 现场生成 Flask `eval` 样例，真实执行源码抽取与固定基线查询，在 SARIF 中核对 `app.py:6` 的 `py/code-injection` 命中。
- 新配置端口、随机密码生成、已有配置保留及原生 UI 隔离检查通过。

本次没有调用 AI 服务，未测试容器内完整复审/报告生成流程；未验证 Windows 真机启动，也未执行尚未接入的隔离修复验证。容器默认是新的独立工作空间，访问 <http://localhost:5181>。
