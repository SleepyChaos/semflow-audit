# 主机开发环境补充

2026-11-16 按当前 Compose、初始化脚本和 Vite 配置核对。完整 Docker 服务的安装、启动、停止和更新统一见 [Docker 启动说明](../DOCKER.md)；本文仅用于需要在主机调试源码的开发者，命令按 macOS/Linux shell 编写，Windows 可使用 WSL2。

## 开发依赖

| 依赖 | 版本依据 / 用途 |
| --- | --- |
| Python 3.14、uv | API、Worker、迁移；工作区依赖以 `uv.lock` 为准 |
| Node.js 22+、npm | 前端；依赖以 `frontend/package-lock.json` 为准 |
| Docker Desktop / Compose | PostgreSQL、Redis、隔离验证镜像 |
| CodeQL CLI 2.23.5 | 主机扫描和规则编译，使用需符合其许可 |
| Python 3.11 | CodeQL 抽取器，与 API Python 分开准备 |

## 主机调试流程

先停止正在运行的完整 Docker 服务（见统一启动说明），避免端口冲突、共用产物目录或两个 Worker 消费同一队列。下面命令从仓库根目录开始；开发数据库使用 `semflow-audit-ui` 项目，与完整 Docker 的 `semflow-audit` 卷独立。

```sh
cd system
python3 scripts/init_local.py
uv sync --project backend --group dev --locked
npm ci --prefix frontend
docker compose -f compose.yml --env-file ../.env -p semflow-audit-ui up -d --wait
```

初始化脚本只在缺少根目录 `.env` 时生成随机密码，不覆盖已有文件。不要先复制空密码模板再运行脚本。主机进程读取 `.env`，Compose 只负责数据库：请将 `DATABASE_URL` 和 `REDIS_URL` 的端口与 `UI_DB_PORT`、`UI_REDIS_PORT` 对齐。当前数据库 Compose 默认端口为 15440/16380，初始化脚本历史默认值为 15439/6389，需要在启动主机进程前核对并调整。密码必须与已有卷一致。

| 配置项 | 使用默认数据库端口时的值 |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://audit:<POSTGRES_PASSWORD>@127.0.0.1:15440/audit` |
| `REDIS_URL` | `redis://127.0.0.1:16380/0` |
| `FRONTEND_HOST` | `http://localhost:5174` |
| `CODEQL_BIN` / `CODEQL_PYTHON_BIN` | `codeql` / `python3.11` |
| `ARTIFACT_ROOT` / `CODEQL_PACK_PATH` | 仓库根目录 `artifacts` / `artifacts/packs` |

准备主机工具和隔离验证镜像（仍在 `system/`）：

```sh
mkdir -p ../artifacts/packs
codeql pack download --dir "$PWD/../artifacts/packs" codeql/python-queries@1.6.0 codeql/javascript-queries@1.4.0
.venv/bin/python scripts/install_query_sources.py
docker build -t ai-code-audit-validator:local -f runners/Dockerfile.python runners
docker pull node:22-bookworm-slim
```

初始化开发库和检查点：

```sh
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m app.initial_data
../.venv/bin/python -m app.jobs.bootstrap
cd ..
```

分别在三个终端从 `system/` 启动，沿用 Vite 当前的 5174 → 8001 默认代理配置：

```sh
# 终端 1：API
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

```sh
# 终端 2：Worker
cd backend
../.venv/bin/python -m celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
```

```sh
# 终端 3：前端
npm run dev --prefix frontend
```

访问 `http://localhost:5174/`，无需账号。需要使用其他 API 端口时，同步设置 Vite 的 `SEMFLOW_API_PROXY`。macOS 沙箱若限制 SWC 缓存，可设置 `SWC_NATIVE_BINDING_CACHE` 到仓库 `artifacts/swc`。

更新后端代码、切换分支或修改模型配置后，API 与 Worker 都需要重启。API 的 `--reload` 不会更新 Worker 已缓存的模块；先确认 Worker 没有活动、已预取或定时任务，再停止并重新启动。保留原失败记录，通过“新建重跑”验证恢复。

## 模型与知识材料

模型配置和容器模式相同，见 [Docker 本地配置](../DOCKER.md#本地配置和持久化)。所有配置声明参阅 [.env.example](.env.example) 与后端 `app/core/audit_config.py`。没有模型配置仍可进入界面，AI 阶段会报告配置错误；不提供假模型降级。

规则生成还需要知识材料。以下命令仅用于已准备好的主机开发环境：

```sh
# system/backend 目录：基础知识
../.venv/bin/python ../scripts/seed_knowledge.py
```

```sh
# system/ 目录：reference / rule_example 双集合
PYTHONPATH=backend .venv/bin/python scripts/curate_rule_corpus.py --validate --index --per-language 14
```

第二条命令会下载官方资料并执行真实 CodeQL 校验；配置 embedding 时还会调用向量服务。未配置 embedding 可使用 BM25，更换 embedding 空间后需重建索引。首批材料不包含本机后续扩充内容；扩充方案见 [RAG 扩充计划](../design/rag-corpus-expansion-plan.md)。

## 验证与本地文件

代码、构建和真实工具验证统一见[系统验证说明](README.md#代码与-cli-验证)，前端浏览器测试配置见[前端说明](frontend/README.md)。

`.env`、`.venv`、`node_modules`、数据库卷、`artifacts/`、上传源码、扫描数据库和审计产物属于本地环境，不随 Git 克隆复制或提交。构建前端输出到 `backend/app/frontend/`，该目录也不提交。
