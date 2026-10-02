# AI Code Audit

结合 CodeQL 静态分析、AI 主动取证、修复验证和 RAG 规则生成的代码审计平台。

## 已实现：第一阶段

- 登录、ZIP 上传和 Python / JavaScript / TypeScript 语言选择。
- 上传安全检查、不可变快照哈希、用户任务隔离。
- Celery 调度 LangGraph：CodeQL 建库 → 扫描 → 保存原始告警和证据。
- 任务状态、日志、失败重试（创建独立执行记录）、漏洞位置、源码与数据流展示、SARIF 下载。
- PostgreSQL 保存业务记录与 LangGraph 检查点。

Python 和 JavaScript 漏洞样本已完成真实端到端扫描，分别检出 `py/code-injection` 和 `js/code-injection`。TypeScript 使用相同抽取器，尚未单独验收。AI 复审、修复与报告、RAG 规则三个阶段当前仅展示功能边界，尚未调用模型或实现业务。

## 本地启动

需要 Docker Desktop、uv、Node.js 22+、CodeQL CLI 2.23.5、Python 3.11（CodeQL 抽取器）。API 使用 Python 3.14，依赖由 uv 安装。CodeQL 使用前请确认其许可适用于目标代码。

在仓库根目录执行：

```sh
python3 scripts/init_local.py
uv sync --project backend --group dev --locked
npm ci --prefix frontend
docker compose up -d --wait
mkdir -p artifacts/packs
codeql pack download --dir "$PWD/artifacts/packs" codeql/python-queries@1.6.0 codeql/javascript-queries@1.4.0
```

初始化数据库：

```sh
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.initial_data
../.venv/bin/python -m app.jobs.bootstrap
```

三个终端分别启动（前两条从 backend 目录执行，第三条从仓库根目录执行）：

```sh
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
../.venv/bin/celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
npm run dev --prefix frontend -- --host 127.0.0.1
```

打开 http://localhost:5173。管理员账号、随机密码保存在本地 `.env`，初始化脚本不会覆盖已有设置。配置选项见 `.env.example` 与 `backend/app/core/audit_config.py`。

## 验证

```sh
.venv/bin/pytest tests/test_audit_core.py tests/test_audit_api.py -q
npm run build --prefix frontend
```

API 测试需要数据库已初始化；使用独立临时用户并清理自己的记录。真实扫描验收可运行 `.venv/bin/python scripts/verify_live.py`，需 API、Worker 与 CodeQL 已启动；JavaScript 验收增加 `--language javascript`。开发服务器可能需要设置 `SWC_NATIVE_BINDING_CACHE` 到可写目录。

## 运行边界

当前为本地开发版本，只审计可信代码。扫描进程无 shell、清理敏感环境变量并限制时间/内存，但尚未实现每任务容器隔离。Worker 异常退出后的运行中任务恢复、取消、产物过期清理及完整生产部署属于后续工作。检查点已保存，不代表外部命令自动恢复或恰好执行一次。

## 设计文档

- [功能链路与 GUI 流程](docs/product-workflow.md)
- [技术栈与模块边界](docs/architecture.md)
- [模板来源](docs/upstream.md)
- [编码与解耦规范](AGENTS.md)

后续顺序：AI 复审与取证 → 确认机制 → 修复与报告 → RAG 规则验收。
