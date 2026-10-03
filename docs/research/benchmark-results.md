# 已执行测试与基准结果

2026-10-03（北京时间）。全部通过代码/API/CLI执行，没有 GUI 测试。结果为本地开发原型的有限校准，不是论文最终实验。

## 1. 开发验证

- 普通测试：**50 passed, 1 deselected**（排除真实工具集成项）。覆盖任务隔离、失败/取消/重试、证据真实性、候选确认、快照篡改、补丁范围、规则正反例/发布门槛、实际 BM25/pgvector 存取与模型协议。
- 真实四阶段集成：**1 passed，60.49s**。CodeQL真实扫描→测试替身AI复审→人工确认→隔离补丁→Docker验证与CodeQL复扫→实际知识检索→QL编译→LangGraph人工暂停/恢复→真实正反例查询→发布→新上传冻结补充规则→报告。
- 集成中的模型回复为明确测试替身，不证明真实 LLM 审计/生成质量。生产适配器没有假模型模式。
- GitHub CI：代码提交 `f584399` 的 push/PR 两次 Application checks 均成功，backend/frontend通过；[执行记录](https://github.com/SleepyChaos/ai-code-audit/actions/runs/37093614320)。
- Ruff通过；Biome检查通过；TypeScript/Vite生产构建通过（macOS使用可写SWC缓存）。Alembic check 无遗漏迁移。
- JS Docker独立验收：JS语法通过；TS跳过编译与0条测试进入 needs_review；实际Node测试通过。Python验证镜像已经按锁定Dockerfile重建。

## 2. 审计：12个自建正反例，3轮重复

每语言6例，3个漏洞版+3个良性版，覆盖代码/命令/SQL注入（CWE-094/078/089）。按目标文件+精确行+CWE映射匹配，一例多告警只计一次。CodeQL固定2.23.5与python-queries1.6.0/javascript-queries1.4.0；Bandit1.9.4。

| 工具 | 独立例数 | TP/FP/FN/TN | 目标Precision/Recall | 总耗时中位数 | 三轮范围 | 每轮全部告警 |
|---|---:|---|---|---|---|---:|
| CodeQL python | 6 | 3/0/0/3 | 1.00 / 1.00 | 10.747s | 10.335–13.028s | 3 |
| CodeQL javascript | 6 | 3/0/0/3 | 1.00 / 1.00 | 17.303s | 17.049–17.720s | 8 |
| Bandit Python | 6 | 3/0/0/3 | 1.00 / 1.00 | 0.108s | 0.108–0.157s | 3 |

**100%仅限这12个简单的已标注目标，不代表平台整体准确率。** JS每轮8条总告警，只有3条目标命中，其余5条尚未裁决；不能声称整份报告precision=100%。Bandit B307的自带CWE元数据为078，本实验按其eval检查的语义映射到094，映射已在原始结果保存。

CodeQL每轮新建数据库；OS/查询缓存没有清空，所以不能称严格冷启动。计时含抽取+扫描+解析，不含API排队/ZIP上传/模型。Bandit计时含进程启动+AST检查，二者分析深度不同；微样本体现开销，不能据此推断大仓库谁更好。

## 3. 真实JS CVE单文件探索

OpenSSF三个pre/post配对，固定commit，未运行第三方代码。建库一次，每份数据库查询三轮，pre每轮5条、post每轮3条。额外告警可能是该历史版本的其他漏洞，不能全部算误报。

| 目标 | 漏洞版观测 | 官方修复版观测 | 可以说明什么 |
|---|---|---|---|
| CVE-2017-1000427 URL校验 | js/incomplete-url-scheme-check，878行 | 同目标告警消失；另有历史ReDoS告警 | 该单文件目标修复识别有效 |
| CVE-2017-16114 ReDoS | js/redos，459行两处 | 459行仍有一处js/redos | 需独立oracle确认剩余路径/根因，不能直接判FP或修复失败 |
| CVE-2018-16487 原型污染 | 无告警 | 无告警 | 当前固定规则+单文件上下文未识别目标；必须扩完整仓库/规格模型研究 |

这组结果更适合暴露能力边界；样本与上下文太少、真值尚未独立执行，不给完整仓库召回或修复准确率。

## 4. 修复：3类提供的候选，9次容器验证

四个独立行为测试：整数、加法、减法、拒绝函数调用。测试没有由修复模型生成；工作区只读、无网络、非root，原文件hash不变。

| 提供的候选 | 结果 | 验证中位数 |
|---|---|---|
| unsafe_eval | failed（3轮一致） | 0.369s |
| secure_but_breaks_behavior | failed（3轮一致） | 0.367s |
| bounded_arithmetic | passed（3轮一致） | 0.358s |

不安全eval的功能测试通过但安全测试失败；int转换能拒绝攻击却破坏加减功能；受限AST算术同时通过。证明当前验证链能区分这些样例，**不表示AI正确生成率为1/3或100%**。三份都是人工提供的候选。通用语法/复扫依然不足以证明真实修复正确，需要项目双oracle和盲审。

## 5. RAG：实际BM25微型检索

8个原创中英混合文档+8个另行措辞问题，PostgreSQL持久化、实际Haystack BM25，3轮：Recall@3=1.00，MRR@3=0.9375；检索中位数约2.5–3.0ms。共享种子文档仍可参与检索，来源/版本/digest均可记录。

这是小型检索功能实验；没有真实embedding或LLM，所以不评估向量语义质量，也不宣称RAG提高规则准确率。真实QL编译与正反例已有集成验证，但仍使用固定模型回复；独立规则留出评价见experiment-plan.md。

## 6. 原始证据与重跑

本地原始产物（不会提交真实上传内容或PDF）：

- `artifacts/benchmarks/e244a60d-c380-45da-9839-50c656acea03/report.json`：6次CodeQL扫描与9次修复验证；源码、SARIF、日志和hash在同目录。
- `artifacts/benchmarks/e244a60d-c380-45da-9839-50c656acea03/bandit-report.json`：3轮竞品结果，Bandit依赖清单为artifacts/competitors/bandit-freeze.txt。
- `artifacts/benchmarks/real-js-4818f4cc-78cd-451b-a306-26d6775873f3/report.json`：真实pre/post、所有告警和计时。
- `artifacts/benchmarks/rag-23c029ef-6ca1-4441-b3fa-ad6c487dc0e3/report.json`：24次实际检索、排名与引用。

- artifacts/final-integration.log、artifacts/js-validator-verification/report.json：真实链路与JS容器校准。
- benchmark-summary.json：可随Git提交的原创样本结果与统计副本；第三方源码/论文保持artifacts中，许可与hash独立保存。

```sh
uv venv --python python3.11 artifacts/competitors/bandit-venv
uv pip install --python artifacts/competitors/bandit-venv/bin/python -r docs/research/bandit-requirements.txt
.venv/bin/python scripts/benchmarks/run_local.py --rounds 3
.venv/bin/python scripts/benchmarks/bandit_baseline.py artifacts/benchmarks/<运行ID>/report.json
.venv/bin/python scripts/benchmarks/rag_retrieval.py
.venv/bin/python scripts/benchmarks/real_cve_scan.py
```

## 7. 尚未执行的准确率实验

真实模型服务未配置，因此本平台真实AI复审、补充发现、patch生成与规则生成准确率、阿里LLM竞品和混合向量检索质量均待测。Semgrep尚未实跑。完整项目CVE/双oracle、按项目留出/根因去重/置信区间需要下一批实验。

第三贡献建议基于此次修复反例收紧：共享证据下的独立安全+功能验收与经验证反馈，而不以“扫描告警下降”作正确修复证明。
