# AI Code Audit

结合 CodeQL 静态分析、AI 取证复审、隔离修复验证与 RAG 规则生成的四阶段审计原型。当前支持 Python 与 JavaScript/TypeScript 的 CodeQL 扫描。

## 四阶段能力

1. **CodeQL 审计**：ZIP 上传检查、不可变快照、固定查询包、原始 SARIF/源码/数据流、独立重试与取消、长期无进展执行回收。可选冻结最多 4 个已发布补充规则版本。
2. **AI 复审**：按告警/路径选择范围，有限预算读取源码、搜索/调用线索、检索知识与执行已批准查询。所有结论关联真实证据；模型建议与人工确认分离，证据不足可弃权。
3. **修复与报告**：只处理人工确认目标，限定文件，隔离副本精确补丁与 diff，Docker 语法/项目测试与冻结规则复扫。检查通过后人工接受；不会直接改写原上传源码。JSON/Markdown 报告保留历史与版本。
4. **RAG 规则**：持久化、版本化知识块，实际 Haystack BM25 与可选 pgvector 混合检索，引用来源/版本/digest。策略选择、固定依赖、有限编译反馈、人工批准正反例、真实 CodeQL 验收后发布或退役。人工等待通过 LangGraph interrupt 释放 Worker。

## 本地启动

需要 Docker Desktop、uv、Node.js 22+、CodeQL CLI 2.23.5、Python 3.11（抽取器）；API 使用 Python 3.14。依赖与模板提交均已锁定。CodeQL 的使用需符合其许可。

```sh
python3 scripts/init_local.py
uv sync --project backend --group dev --locked
npm ci --prefix frontend
docker compose up -d --wait
mkdir -p artifacts/packs
codeql pack download --dir "$PWD/artifacts/packs" codeql/python-queries@1.6.0 codeql/javascript-queries@1.4.0
.venv/bin/python scripts/install_query_sources.py
docker build -t ai-code-audit-validator:local -f runners/Dockerfile.python runners
docker pull node:22-bookworm-slim
```

初始化数据库及知识（在 backend 目录）：

```sh
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.initial_data
../.venv/bin/python -m app.jobs.bootstrap
../.venv/bin/python ../scripts/seed_knowledge.py
```

设置根目录 `.env` 中的 `AI_BASE_URL`、`AI_MODEL`、`AI_API_KEY`（OpenAI 兼容服务）。可选 `EMBEDDING_MODEL` 需要同一网关支持 embeddings；没有配置向量服务仍支持实际 BM25。重启 API 与 Worker 后配置生效；生产模块没有假模型降级。

三个终端启动，前两条从 backend 目录、第三条从仓库根目录：

```sh
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
../.venv/bin/celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
npm run dev --prefix frontend -- --host 127.0.0.1
```

打开 http://localhost:5173；随机管理员密码保存在 `.env`。初始化脚本不覆盖已有配置。macOS 沙箱若限制 SWC 缓存，可设置 `SWC_NATIVE_BINDING_CACHE` 到仓库 `artifacts/swc`。

## 代码与 CLI 验证

```sh
.venv/bin/pytest -m 'not integration' -q
AUDIT_RUN_REAL_TOOLS=1 .venv/bin/pytest tests/test_pipeline_live.py -q
npm run build --prefix frontend
.venv/bin/python scripts/benchmarks/run_local.py --rounds 3
.venv/bin/python scripts/benchmarks/rag_retrieval.py
```

普通测试需本地数据库已初始化。集成测试使用真实 CodeQL、Docker、PostgreSQL、LangGraph 检查点；模型回复为明确标注的测试替身，因此验证流程，不证明 LLM 准确率。测试只清理自己临时用户和线程记录。按照用户要求没有执行 GUI 测试。

## 实际边界

- 这是可信本地代码的研究原型。CodeQL 仍运行在主机，尚未做逐任务扫描容器隔离；修复运行验证有 Docker 限制。
- 没有真实模型配置时，AI 阶段不能执行。已有流程测试不等于真实审计/修复生成质量实验。
- 调用者工具为语法/文本线索；`new_location` 表示不同位置，不证明独立漏洞根因。新增漏洞需人工确认和根因去重。
- 通用验证镜像不自动安装项目依赖；TS/JSX 编译需要项目专用验证器，不能以跳过编译算通过。语法、复扫和模型自生成例不构成正确性证明。
- 暂不包含自动 exploit 注册、反馈知识自动发布、完整生产部署/清理策略。知识来源 URL 仅记录，不自动访问。
- 取消在当前外部调用结束后于阶段边界生效。回收阈值 45 分钟；旧执行保留，新重试创建独立快照记录。

## 交付文档

- [用户校准清单](docs/acceptance-checklist.md)
- [早期聊天回顾](docs/research/history-review.md)
- [完整论文与竞品实验方案](docs/research/experiment-plan.md)
- [实际基准结果](docs/research/benchmark-results.md)
- [论文与三项贡献建议](docs/research/papers-and-innovations.md)
- [竞品与下载材料](docs/research/competitors-and-materials.md)
- [下一阶段总计划：规则生成、审计效果、速度](docs/research/phase-two-master-plan.md)
- [第二阶段首批改进与真实模型/完整仓库基准](docs/research/phase-two-results.md)
- [功能链路与 GUI 流程](docs/product-workflow.md)
- [模块边界](docs/architecture.md)、[模板来源](docs/upstream.md)、[编码约束](AGENTS.md)
