# 协作者本地环境与启动清单

更新日期：2026-10-18。跨平台协作推荐使用 [Docker 启动方案](docker/README.md)，宿主机无需安装 Python、Node 和 CodeQL。下面保留 macOS/Linux 原生开发方式，服务地址以 `system/.env.example` 为准；已有本地配置不会自动修改。版本表为原生开发环境的参考，安装以锁文件为准，容器版本见 Dockerfile。

## 运行环境

| 项目 | 当前本地版本 / 配置 | 用途 |
| --- | --- | --- |
| 系统 | macOS 15.7.2，Apple Silicon / arm64 | 当前验证平台 |
| API Python | 3.14.6 | FastAPI、Worker、数据库迁移 |
| CodeQL 抽取 Python | 3.11.15，命令 `python3.11` | 与 API Python 分开安装 |
| uv | 0.11.2 | 安装 `system/` 工作区 `.venv` |
| Node.js / npm | 26.0.0 / 11.12.1 | 前端构建与开发服务器 |
| Docker / Compose | 29.5.2 / v5.1.3 | PostgreSQL、Redis、隔离修复验证 |
| CodeQL CLI | 2.23.5，命令 `codeql` | 固定扫描和规则编译工具版本 |
| PostgreSQL 镜像 | `pgvector/pgvector:pg17` | 审计记录、LangGraph 检查点、向量索引 |
| Redis 镜像 | `redis:7.4.2-alpine` | Celery 任务队列 |
| Python 验证镜像 | `ai-code-audit-validator:local` | 从 `runners/Dockerfile.python` 本地构建 |
| JS 验证镜像 | `node:22-bookworm-slim` | 修复隔离验证；与主机 Node 版本独立 |

主要已安装依赖：React 19.3.0、Vite 8.3.2、TypeScript 6.0.3、Playwright 1.62.1；FastAPI 0.141.1、SQLModel 0.0.39、LangGraph 1.2.12、Haystack 3.3.0、OpenAI SDK 3.24.0、psycopg 3.3.4、Celery 5.6.3、Redis Python 客户端 6.4.0。

## 服务与端口

| 服务 | 本机地址 | 配置 |
| --- | --- | --- |
| 工作台 | `http://127.0.0.1:5174/` | 可以直接访问 |
| API / 文档 | `http://127.0.0.1:8000` / `/docs` | 前端 `/api` 由 Vite 代理到此地址 |
| PostgreSQL | `127.0.0.1:15440` | 用户 `audit`、库 `audit`，容器端口 5432 |
| Redis | `127.0.0.1:16380/0` | 容器端口 6379 |
| Celery Worker | 无 HTTP 端口 | 需要单独启动才能执行后台审计阶段 |

环境变量保存在仓库根目录 `.env`，API 与 Worker 共用。前端当前使用同源 API 代理，无需配置 `frontend/.env` 中旧的 `VITE_API_URL`、`MAILPIT_HOST`。浏览器没有用户注册、登录或令牌要求。

## 当前配置项

以下为新安装模板及模型配置示例。路径 `<repo>` 表示协作者自己的仓库路径。密码和密钥不随仓库分发。

| 配置项 | 当前值 / 协作者填写方式 |
| --- | --- |
| `PROJECT_NAME` | `AI Code Audit`（界面品牌为 SemFlow Audit） |
| `FASTAPI_ENV` | `development` |
| `FRONTEND_HOST` | `http://127.0.0.1:5174` |
| `POSTGRES_PASSWORD` | 本地已配置；协作者由初始化脚本生成自己的密码 |
| `DATABASE_URL` | `postgresql+psycopg://audit:<本机密码>@127.0.0.1:15440/audit` |
| `REDIS_URL` | `redis://127.0.0.1:16380/0` |
| `ARTIFACT_ROOT` | `<repo>/artifacts` |
| `CODEQL_BIN` / `CODEQL_PYTHON_BIN` | `codeql` / `python3.11` |
| `CODEQL_PACK_PATH` | `<repo>/artifacts/packs` |
| `PYTHON_QUERY_PACK` | `codeql/python-queries@1.6.0` |
| `JAVASCRIPT_QUERY_PACK` | `codeql/javascript-queries@1.4.0` |
| `AI_BASE_URL` | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| `AI_MODEL` | `deepseek-v4.1-flash` |
| `AI_API_KEY` | 本地已配置；协作者填写自己有权限使用的密钥 |
| `AI_THINKING_MODE` | `disabled` |
| `AI_TIMEOUT` / `AI_MAX_OUTPUT_TOKENS` | 90 秒 / 6000 |
| `AI_SCOUT_TOKENS` / `AI_RULE_TOKENS` | 3000 / 6000 |
| `AI_REVIEW_TOKENS` / `AI_REPAIR_TOKENS` | 0 / 0（继承全局输出预算 6000） |
| `AI_AUDIT_EXECUTION_MODE` | `progress`，持续取得进展时继续执行；`bounded` 使用阶段总限额 |
| `AI_STAGE_MAX_CALLS` / `AI_STAGE_MAX_TOKENS` / `AI_STAGE_MAX_SECONDS` | 24 / 100000 / 300 秒 |
| `EMBEDDING_MODEL` | 留空，默认 BM25 |
| `EMBEDDING_REVISION` | 留空 |
| `EMBEDDING_DIMENSIONS` | 0 |
| `SEMANTIC_CONTEXT_CHARS` / `SEMANTIC_TOOL_LIMIT` | 40000 / 8 |
| `REPAIR_ATTEMPTS` / `VALIDATOR_TIMEOUT` | 3 / 120 秒 |
| `VALIDATOR_PYTHON_IMAGE` / `VALIDATOR_JS_IMAGE` | 见运行环境表 |
| `SCAN_TIMEOUT` / `CODEQL_THREADS` / `CODEQL_RAM` | 900 秒 / 2 / 2048 MB |
| `UPLOAD_LIMIT` / `EXTRACT_LIMIT` / `FILE_LIMIT` | 20 MiB / 100 MiB / 2000 文件 |
| `REVIEW_QUERY_LIMIT` | 3 |

本地使用的服务地址和模型名称仅供复现；协作者需确认自己的服务权限。也可以配置其他 OpenAI 兼容服务。未配置模型时仍可进入界面，AI 阶段会报告配置错误；默认没有 embedding 配置，使用 BM25 检索；只有另行启用或更换 embedding 空间时才需要相应服务并重建向量索引。

新安装无需 `SECRET_KEY`、管理员密码或 SMTP 配置。`FIRST_SUPERUSER` 仅用于旧数据库历史记录的归属兼容；迁移旧库且原管理员邮箱不同于默认值时保留原配置。

## 从全新克隆启动

先安装并启动 Docker Desktop，安装上表中的 Python、uv、Node 和 CodeQL，确认 `codeql` 和 `python3.11` 在 `PATH` 中。CodeQL 使用需符合其许可。

```sh
git clone https://github.com/SleepyChaos/semflow-audit.git
cd semflow-audit/system
python3 scripts/init_local.py
uv sync --project backend --group dev --locked
npm ci --prefix frontend
docker compose --env-file ../.env -p semflow-audit up -d --wait
```

初始化脚本不会覆盖已有 `.env`。不要先复制空密码的 `.env.example` 再运行脚本，否则会保留空值。数据库密码必须与 `DATABASE_URL` 中的密码一致；已有数据库卷不会因修改 `.env` 自动修改数据库密码。

编辑新生成的根目录 `.env`，按需要追加模型配置，例如复用当前服务类型：

```dotenv
AI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
AI_MODEL=deepseek-v4.1-flash
AI_API_KEY=<协作者自己的密钥>
AI_THINKING_MODE=disabled
AI_RULE_TOKENS=6000
EMBEDDING_MODEL=
EMBEDDING_REVISION=
EMBEDDING_DIMENSIONS=0
```

如只查看界面，可先不添加这些模型配置。以下在 `system/` 目录准备扫描工具和验证镜像：

```sh
mkdir -p ../artifacts/packs
codeql pack download --dir "$PWD/../artifacts/packs" codeql/python-queries@1.6.0 codeql/javascript-queries@1.4.0
.venv/bin/python scripts/install_query_sources.py
docker build -t ai-code-audit-validator:local -f runners/Dockerfile.python runners
docker pull node:22-bookworm-slim
```

初始化数据库、检查点和基础知识：

```sh
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m app.initial_data
../.venv/bin/python -m app.jobs.bootstrap
../.venv/bin/python ../scripts/seed_knowledge.py
cd ..
```

完整执行默认 rule v8 还需要 reference / rule_example 双集合。从 `system/` 目录运行下面的采集、核验和索引命令（会下载官方资料、执行真实 CodeQL 校验；已配置 embedding 时会调用向量服务）：

```sh
PYTHONPATH=backend .venv/bin/python scripts/curate_rule_corpus.py --validate --index --per-language 14
```

上面的命令准备首批材料；本机后续扩充的知识、数据库数据和实验材料不自动随 Git 克隆复制。完整材料扩充方案见 [RAG 扩充计划](../design/rag-corpus-expansion-plan.md)。

分别在三个终端启动，以下都从 `system/` 目录执行：

```sh
# 终端 1：API
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```sh
# 终端 2：Worker
cd backend
../.venv/bin/python -m celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
```

```sh
# 终端 3：前端
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5174 --strictPort
```

打开 `http://127.0.0.1:5174/`，直接进入工作台。若端口被占用，应释放端口或同步调整配置；模型配置修改后重启 API 和 Worker。API 使用其他端口时，在前端进程设置 `SEMFLOW_API_PROXY=http://127.0.0.1:<端口>`。macOS 沙箱若限制 SWC 缓存，在前端命令前加 `SWC_NATIVE_BINDING_CACHE="$PWD/../artifacts/swc"`。

## 验证与本地文件

```sh
.venv/bin/python -m pytest -m 'not integration' -q
npm run build --prefix frontend
# 首次安装浏览器测试运行时
cd frontend
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 npm test
```

上述浏览器测试需要正在运行的 API 和前端；已安装桌面 Chrome 时可添加 `PLAYWRIGHT_CHANNEL=chrome` 使用它。真实 CodeQL/Docker 集成测试按根目录 README 单独启用；它们不证明真实模型的审计准确率。

`.env`、`.venv`、`node_modules`、数据库卷、`artifacts/`、上传源码、扫描数据库和审计产物都属于本地环境。克隆后自行安装或重新生成，不提交密钥、真实上传项目或审计产物。构建后的前端输出到 `backend/app/frontend/`，该目录也不提交。
