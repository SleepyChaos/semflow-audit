# SemFlow Audit

`SemFlow` 表示 Semantic Flow，围绕语义理解与数据流分析构建代码审计平台。当前工作已于 2026-10-09 迁入该项目；代码、研究设计、实验脚本和材料索引共同维护。

- [仓库目录与资料归档](docs/repository-layout.md)、[文档导航](docs/README.md)、[脚本导航](scripts/README.md)
- [已收集论文与阅读材料](benchmark-data/papers/README.md)、[测试数据压缩包与恢复方法](benchmark-data/datasets/README.md)
- [LLM 与 CodeQL 协同方案索引](docs/research/codeql-llm-proposals-index.md)
- [CodeQL 分析中段介入 LLM 的详细设计](docs/research/codeql-intermediate-llm-design.md)
- [工作区迁移说明](docs/workspace-migration.md)
- [协作者本地环境与启动清单](docs/collaborator-setup.md)
- [测试结果、环境与版本归档](docs/testing/README.md)
- [2026-10-09 新样本补测与失败记录](docs/research/supplemental-20261009-results.md)
- [各链路最新测试情况与用途（仍有未完成环节）](docs/research/chain-completion-20261009-results.md)

结合 CodeQL 静态分析、AI 取证复审、隔离修复验证与 RAG 规则生成的四阶段审计原型。当前支持 Python 与 JavaScript/TypeScript 的 CodeQL 扫描。

## 四阶段能力

1. **双引擎发现**：新上传默认 pipeline v2，同一不可变快照并发执行 CodeQL 标准 code-scanning 套件与独立 Agent 源码粗筛。粗筛不输入静态告警或关键词锚点，按模块轮转分窗，可跨文件只读补证；保存未知前提、候选与部分覆盖。可选冻结最多 4 个已发布补充规则版本；不默认启用扩展套件。
2. **统一复核**：新阶段默认 review v4，分批核查 CodeQL 与粗筛候选。支持/排除需要已检查前提与实际源码，排除还需反证，未决不自动排除；重新评估粗筛未知前提。根因关联只提建议，原始候选和触发路径保留。模型建议与人工确认分离；确认后可进入修复与规则生成。历史 v1–v3 配置保留。
3. **修复与报告**：默认 v2，项目/目标流程/修改点语义解释、有限只读取证、证据引用与关键未知阻断；最多三个隔离候选，沿用 Docker 语法/所选项目测试与冻结规则复扫，失败诊断反馈。保存 Diff/历史并人工接受。语义解释不等于业务正确性证明。
4. **RAG 规则**：默认 v8（漏洞检测用途），实际源码＋漏洞描述＋reference/rule_example 双集合；固定版本 BM25/pgvector/RRF、真实 embedding 和角色召回。源码准备与生成阶段分工、完整原文精简视图、支持范围内类型化规格/官方模板与有限实际 API source 扩展；有限候选反馈、真实编译/开发正反例、原项目单规则执行与人工根因确认，保留样例批准、独立验收、发布门。无 reranker；原有人工批准通过 LangGraph interrupt 释放 Worker。

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

本次配置 `EMBEDDING_MODEL=doubao-embedding-vision`、`EMBEDDING_REVISION=doubao-embedding-vision-251215`、`EMBEDDING_DIMENSIONS=2048`；更换空间需重建索引。模型协议显式使用 `AI_THINKING_MODE=disabled`、`AI_RULE_TOKENS=6000`，阶段恢复沿用已冻结配置。新 rule v8 需要两个集合都有匹配版本材料；首批资料可从仓库根目录采集、核验及索引：

```sh
PYTHONPATH=backend .venv/bin/python scripts/curate_rule_corpus.py --validate --index --per-language 14
```

三个终端启动，前两条从 backend 目录、第三条从仓库根目录：

```sh
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
../.venv/bin/celery -A app.jobs.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO
npm run dev --prefix frontend -- --host 127.0.0.1
```

打开 http://localhost:5173，直接进入本地审计工作台，无需账号或登录。初始化脚本不覆盖已有配置。macOS 沙箱若限制 SWC 缓存，可设置 `SWC_NATIVE_BINDING_CACHE` 到仓库 `artifacts/swc`。

## 代码与 CLI 验证

```sh
.venv/bin/pytest -m 'not integration' -q
AUDIT_RUN_REAL_TOOLS=1 .venv/bin/pytest tests/test_pipeline_live.py -q
npm run build --prefix frontend
.venv/bin/python scripts/benchmarks/run_local.py --rounds 3
.venv/bin/python scripts/benchmarks/rag_retrieval.py
```

普通测试需本地数据库已初始化。集成测试使用真实 CodeQL、Docker、PostgreSQL、LangGraph 检查点；模型回复为明确标注的测试替身，因此验证流程，不证明 LLM 准确率。测试只清理自己临时用户和线程记录。前端无账号入口的浏览器验证可运行 `npm test --prefix frontend`；默认从空浏览器存储开始。

## 实际边界

- 这是可信本地代码的研究原型。CodeQL 仍运行在主机，尚未做逐任务扫描容器隔离；修复运行验证有 Docker 限制。
- 没有真实模型配置时，AI 阶段不能执行。已有流程测试不等于真实审计/修复生成质量实验。
- 独立粗筛默认最多 24 个窗口、每窗口 3 步，全阶段最多 24 次调用；大项目可能仅部分覆盖。复核默认每批 4 个候选、最多 24 批，仍受全阶段调用/时间/token预算约束。
- 调用者工具为语法/文本线索；`new_location` 表示不同位置，不证明独立漏洞根因。新增漏洞需人工确认和根因去重。
- 通用验证镜像不自动安装项目依赖；TS/JSX 编译需要项目专用验证器，不能以跳过编译算通过。语法、复扫和模型自生成例不构成正确性证明。
- 稳定化评价限定于Python/JavaScript eval、SQL、反射XSS六类任务各三轮；固定Python库的部分路由覆盖仍不足。复审锚点/框架建模/其他策略仍属自由QL实验草稿，语法、开发样例和材料数量不替代新任务准确率。
- 暂不包含自动 exploit 注册、反馈知识自动发布、完整生产部署/清理策略。知识来源 URL 仅记录，不自动访问。
- 取消在当前外部调用结束后于阶段边界生效。回收阈值 45 分钟；旧执行保留，新重试创建独立快照记录。

## 交付文档

- [正式实验计划与跨上下文续接状态](benchmark-data/experiments/README.md)
- [2026-10-05 首轮三链路基准测试及论文比较](benchmark-data/experiments/calibration-results.md)
- [漏洞发现整改及同项目复测结果](benchmark-data/experiments/discovery-retest-results.md)
- [输入/检查任务覆盖整改与完整开发集复测](benchmark-data/experiments/discovery-coverage-results.md)
- [三条创新链路的专业基准材料目录与评测协议](benchmark-data/README.md)
- [双引擎发现开发计划](docs/dual-engine-development-plan.md)
- [双引擎实现结果与真实模型开发测试](docs/research/dual-engine-development-results.md)
- [双引擎 GUI 验收清单（由用户执行）](docs/dual-engine-acceptance-checklist.md)

- [规则稳定化结果与198次新请求消融](docs/research/rag-stabilization-results.md)
- [用户校准清单](docs/acceptance-checklist.md)
- [两模块改造结果、真实对照与消融](docs/research/semantic-development-results.md)
- [新旧 RAG 原测试集复测：旧 K 15/18、新 v6 auto 1/18（共同预算 6000）](docs/research/legacy-rag-matched-results.md)
- [RAG 扩充结果：271 知识原文、141 完整范例与质量分层](docs/research/rag-corpus-expansion-results.md)
- [下一批知识与范例扩充目标](docs/rag-corpus-expansion-plan.md)
- [两模块 GUI 校准清单（由用户执行）](docs/semantic-development-checklist.md)
- [早期聊天回顾](docs/research/history-review.md)
- [完整论文与竞品实验方案](docs/research/experiment-plan.md)
- [实际基准结果](docs/research/benchmark-results.md)
- [论文与三项贡献建议](docs/research/papers-and-innovations.md)
- [竞品与下载材料](docs/research/competitors-and-materials.md)
- [下一阶段总计划：规则生成、审计效果、速度](docs/research/phase-two-master-plan.md)
- [修复与规则生成模块后续开发改造总方案](docs/repair-rule-development-plan.md)
- [业务语义修复编排与后续验证计划](docs/semantic-repair-plan.md)
- [RAG 知识与规则范例双集合方案](docs/rag-two-corpus-plan.md)
- [第二阶段首批改进与真实模型/完整仓库基准](docs/research/phase-two-results.md)
- [功能链路与 GUI 流程](docs/product-workflow.md)
- [模块边界](docs/architecture.md)、[模板来源](docs/upstream.md)、[编码约束](AGENTS.md)
