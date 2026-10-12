# 语义修复与双集合规则生成：实现及对比结果

2026-10-04 后续同集复测：旧最强 K 重新运行 **15/18**，当前 v6 默认 auto 在共同旧预算 6000 下 **1/18**。此前本文件的 3/3 仅支持单个开发案例，不能概括为总体改善。完整结果和失败原因见[原测试集对照报告](legacy-rag-matched-results.md)。

日期：2026-10-04。对照基线：`2b1519b`。本次完成两模块的首版机制、真实模型开发案例对比和部分消融；没有完成跨项目准确率评测。聚合原始数据见 [JSON 摘要](semantic-development-summary.json)，开发范围见 [总方案](../../design/repair-rule-development-plan.md)，GUI 由用户按 [清单](../../design/semantic-development-checklist.md) 校准。

## 1. 结论

| 项目 | 实测结果 | 可以得出的结论 |
|---|---|---|
| 规则旧 v2 → 新 v6 | 同一个未建模来源案例，各 3 轮；旧端到端 0/3，新编译、开发正反例、隐藏变体及原项目候选匹配均 3/3 | 新组合在这个开发案例中更稳定；不是总体准确率，也不能归因于单独的 RAG 改动 |
| 修复旧 v1 → 新 v2 | 两个业务案例，各 3 轮；业务检查均 6/6 | 本次没有观察到修复效果提升；分层解释、取证和失败修订机制已实现，需要更难的独立案例验证 |
| hybrid → BM25 | 两者保留角色路由，各 3 轮，规则端到端均 3/3 | 没有证明向量检索优于 BM25；实际 embedding 可用与质量增益是两件分别评价的事 |
| 移除检索角色路由 | 相同双集合、hybrid、源码和反馈；3/3 → 1/3 | 相关 API/知识与范例的装配在该案例中有帮助；还需更多漏洞家族验证 |
| 耗时 | 修复中位数 2.41 → 8.68 秒；新规则含隐藏评价的中位数 96.11 秒 | 修复成本增加约 3.6 倍；旧规则失败时的 12.53 秒不能作为成功任务的加速对照 |

**当前状态应称“证据约束的业务语义理解辅助修复”，不能称业务语义已被证明保持。** 规则原项目结果停在待人工根因/路径确认；本次没有自动确认或发布实验规则。

## 2. 已实现的执行链路

### 2.1 修复 v2

确认目标与快照检查 → 项目清单/文档 → 项目概览、目标流程、修改点三层解释 → 有限只读取证 → 冻结上下文 → 完整候选 → 原版隔离副本 → 已选现有检查 → 失败分类 → 有限候选修订/语义补证 → 保存 Diff、理解依据、检查及人工接受。

- 只读工具：源码窗口、源码搜索、调用线索、项目文档。调用线索不等于完整调用图；读取关联模块不授予修改权限。
- 事实分为 supported/inferred/unknown/conflicting；引用必须来自已读证据，关键 unknown/conflicting 阻断修复。摘要仍是模型解释，服务端没有证明其推理正确。
- 默认最多 3 个完整候选、累计 8 次补证工具请求、12 次语义模型调用，同时受阶段实际请求/token/时间预算约束。阶段恢复使用已冻结预算。
- 实现错误回候选；理解缺口回补证；环境错误停止改代码并保存 needs_review。关键材料不足目前结束阶段，需补资料后创建新阶段，尚无专门的人机澄清 interrupt/API。
- 每个候选从原始快照重建；保存模型输入/输出 receipt、候选、Diff、检查日志与哈希。接受前检查原源码、候选、工作区、Diff、上下文与验证身份。
- 沿用语法/所选项目测试及可选冻结规则复扫。没有新增利用重放、安全 oracle、业务回归矩阵或精细静态差分。

主要落点：`services/semantic_inspection.py`、`context_materials.py`、`repair_semantics.py`、`repair_integrity.py`、`workflows/repair.py`、`prompts/repair.v2.txt`。

### 2.2 规则 v6

漏洞描述＋实际源码正文 → 有限语义取证 → 固定版本的 reference/rule_example 独立召回 → 三类材料冻结 → 生成查询/必要模型 → 契约与真实编译 → 开发正反例 → 原项目单入口查询 → 目标/基线匹配 → 人工根因确认 → 保留原有样例批准、独立验收及发布门。

- 没有实际源码或任一知识集合时阻断生成。可使用确认漏洞，或 requirement＋source_paths；后者没有已确认目标，只能标记补漏 not_evaluated。
- 按操作/CWE选择 Query、Customizations、ApiGraphs/DataFlow/TaintTracking 等知识角色和同类范例；未知操作回到通用召回。当前为确定性路由，没有 reranker。
- 范例取回完整查询及必要模块、固定依赖、公开开发测试与验证状态；失败官方样例不进入生成检索。
- 使用真实 `doubao-embedding-vision`、返回版本 `doubao-embedding-vision-251215`、2048 维，与现有 pgvector/BM25/RRF 配合。索引身份包含网关、请求/返回版本、维度、协议和预处理；过期向量不混用，两集合共用一次查询向量。
- 最多两次完整候选。编译、开发执行、原项目目标漏检可反馈；独立隐藏评价不反馈给生成器。
- 模型复制官方 `py/...` 查询 ID 时，服务端只分配 `audit/generated-...` 元数据命名空间，保留原候选；不代写 QL 逻辑。不被入口查询导入的新增模块会被拒绝。
- 原项目复测核对 CLI、查询包、依赖锁、数据库元数据、目标文件完整归档、快照、基线和候选身份。同 CWE/位置只建立待确认关联；不自动算 TP。原基线相近结果需要人工说明为何不是同一根因，已有明确静态来源关联则不算新增覆盖。

主要落点：`adapters/retrieval/dual_corpus.py`、`services/rule_materials.py`、`rule_synthesis.py`、`rule_development.py`、`rule_project_validation.py`、`rule_database_identity.py`、`workflows/rules.py`、`prompts/rule.v6.txt`。路由与图节点继续保持薄，提示词单独版本化。

## 3. 知识与范例材料

首批目标达到：**40 个独立 reference 主题、28 个完整范例，其中 22 个官方开发测试通过，6 个失败并排除出生成检索**。主题数不是 chunk 数；整段原文和每个文件 SHA256/Git blob 校验、MIT 来源及依赖均留存。

| 语言 | 固定来源 commit | 实际库版本 | 查询包 |
|---|---|---|---|
| Python | `4ece8abc3032a266eb4b9839442d8be5084552ea` | `python-all@4.0.10` | `python-queries@1.6.0` |
| JavaScript | `c524a98eb91c769cb2994b8373181c2ebd27c20f` | `javascript-all@2.4.0` | `javascript-queries@1.4.0` |

使用查询包实际 build commit，而非简单采用当前 CLI 的同名发布 commit。官方 `.qlref` 转为本地测试入口时只复制对应原查询，保留官方预期文件，不调整金标来追求通过。Python 抽取器采用 3.11。CLI/库/抽取器兼容失败有原始记录。

原文、完整清单与逐项测试保存在本地 `artifacts/materials/rag-corpus-v2/manifest.json`。材料采集可恢复命令：

```sh
PYTHONPATH=backend .venv/bin/python scripts/curate_rule_corpus.py --validate --index --per-language 14
```

这是开发 RAG 语料，不是独立评测集。当前以官方固定版本 CodeQL 库/规则为主，仍缺跨框架业务说明、更多防护反例、经核验编译修正案例及多语言覆盖。

## 4. 对比与消融协议

模型请求：`deepseek-v4.1-flash`；实际响应：`deepseek-v4-1-flash-260910`。控制组使用 thinking=disabled、规则输出预算 8000、阶段 token 上限 100000；原始默认思考模式的试跑单独保留，不混入最终比较。现已将这两个显式模型设置写入本地配置与示例配置，新阶段冻结设置，历史阶段不改协议。

规则案例：Python `events_api.fetch_event` 的外部来源到 `eval`，原 CodeQL 未建模该来源。隐藏微样例包含改名、跨函数传播和 `int` 后安全反例，仅在生成结束后加入评分副本，不进入 RAG 或反馈。旧/新组使用相同材料冻结和模型配置；新组额外语义、角色检索与工具门槛属于待比较组合。

| 规则组 | 编译 | 开发检查 | 隐藏检查 | 原项目候选匹配 | 总耗时中位数 |
|---|---:|---:|---:|---:|---:|
| 旧 v2 | 0/3 | 0/3 | 0/3 | 0/3 | 12.53 秒（失败） |
| 新 v6，hybrid＋角色路由 | 3/3 | 3/3 | 3/3 | 3/3，均待人工确认 | 96.11 秒 |
| 新 v6，BM25＋角色路由 | 3/3 | 3/3 | 3/3 | 3/3，均待人工确认 | 97.58 秒 |
| 新 v6，hybrid，移除角色路由 | 2/3 | 1/3 | 1/3 | 1/3，待人工确认 | 78.83 秒（含失败） |

旧组有输出契约/元数据失败，故 0→3 是综合工程改造的效果，不是“单独使用 RAG 提升 100%”。没有 pure-vector、去源码、去反馈、仅知识、仅范例的完整因子实验，不能称充分论文级消融。

修复案例：算术表达式（含运算/小数/括号），以及文档路径（保留根目录内绝对/嵌套路径）。各重复三轮，**独立案例只有两个**。生产检查只选择已有语法配置、不复扫；业务评分文件在生成结束后只加入评分副本。新旧分别 6/6，不验证攻击阻断或不存在新漏洞。

| 修复组 | 业务评分通过 | 实际模型调用/次 | 流程中位耗时 | 总输入/输出 token |
|---|---:|---:|---:|---:|
| v1 | 6/6 | 1 | 2.41 秒 | 4062 / 2270 |
| v2 | 6/6 | 2–3 | 8.68 秒 | 31578 / 10111 |

规则耗时包含生成、开发执行、原项目复测和隐藏评价，修复计时是生产图执行，外部业务评分单列，不能互相比快慢。测试曾共享机器并发，缓存条件未严格统一；token 统计为聊天调用，不含 embedding，均不作为正式性能基准或显著性证据。

### 4.1 原始结果索引

以下本地目录内 `report.json` 保留逐次 stage、模型输入/输出身份、调用、错误及工具结果；本仓库不提交审计产物：

- `artifacts/benchmarks/semantic-repair-controlled-20261004`：最终修复对照。
- `artifacts/benchmarks/semantic-rule-final-verified-20261004`：最终规则对照。
- `artifacts/benchmarks/semantic-rule-bm25-20261004`：移除向量召回。
- `artifacts/benchmarks/semantic-rule-unrouted-20261004`：移除角色路由。
- `semantic-rule-20261004`、`semantic-rule-controlled-20261004`、`semantic-rule-refined-20261004`：截断、引用、ID、模块导入和相关性失败的探索记录。
- `semantic-rule-routed-20261004`：首次角色路由通过，未替代最终独立重跑。
- `semantic-rule-final-20261004`：开发执行服务拆分时漏导入造成中断，仅一条旧组记录；保留原因，排除质量比较，已修正并用 final-verified 重跑。
- `semantic-repair-20261004`：默认思考模式试跑，不与显式关闭思考的最终组混合。

### 4.2 复现命令

已配置本地模型、固定 CodeQL packs、Python 3.11、Docker 验证镜像、迁移和语料后，从仓库根目录运行。会产生实际模型费用；不用 GUI。

```sh
AI_THINKING_MODE=disabled AI_RULE_TOKENS=8000 PYTHONPATH=backend .venv/bin/python scripts/benchmarks/semantic_comparison.py --mode repair --rounds 3 --output artifacts/benchmarks/reproduce-repair
AI_THINKING_MODE=disabled AI_RULE_TOKENS=8000 PYTHONPATH=backend .venv/bin/python scripts/benchmarks/semantic_comparison.py --mode rule --rounds 3 --output artifacts/benchmarks/reproduce-rule
AI_THINKING_MODE=disabled AI_RULE_TOKENS=8000 PYTHONPATH=backend .venv/bin/python scripts/benchmarks/semantic_comparison.py --mode rule --versions 6 --rounds 3 --retrieval-mode bm25 --output artifacts/benchmarks/reproduce-bm25
AI_THINKING_MODE=disabled AI_RULE_TOKENS=8000 PYTHONPATH=backend .venv/bin/python scripts/benchmarks/semantic_comparison.py --mode rule --versions 6 --rounds 3 --collection-routing off --output artifacts/benchmarks/reproduce-unrouted
```

## 5. 工程验收

最终完整命令 `PYTHONPATH=backend AUDIT_RUN_REAL_TOOLS=1 .venv/bin/pytest -q`：**113 passed，108.14 秒（111 项普通测试＋2 项真实 CodeQL/Docker 集成）**。改动 Python 文件 Ruff 检查通过，前端 TypeScript/Vite 构建通过。测试包含租户/阶段/快照隔离、缺材料、关键未知阻断、引用纠正、读取/修改边界、三个候选上限、环境错误停止、上下文/工作区/预算篡改失效、恢复不重复调用、完整规则依赖、原项目发布门以及旧版本兼容。

真实 CodeQL/Docker 集成的模型为明确测试替身，证明流程执行；第 4 节才是真实模型质量实验。前端仅做 TypeScript、Vite 构建与改动文件 lint，没有 GUI 测试。

交付时迁移 head 为 `b72f601e9c40`；确认活动用户无运行/排队任务后已重启本项目 API/Worker，并恢复前端。API 健康检查和 `http://127.0.0.1:5173/` 均 HTTP 200。该检查仅确认服务可访问，没有操作 GUI。

## 6. 下一步改进顺序

1. **修复效果**：冻结至少 20 个跨文件/权限/输出契约的独立业务案例，增加直接替换会破坏正常行为的近似例；旧/分层理解/失败反馈分开比较。先证明理解带来收益，再增加语义缓存。利用复测仍按用户决定暂缓，不能依赖暂缓能力给修复成功背书。
2. **规则稳定性**：至少 20 项独立需求覆盖多 CWE/来源/框架，按项目和漏洞家族留出；把旧/新语料、双集合、角色路由、embedding、源码、反馈分开消融。当前优先投入 API 绑定与高质量范例；不以继续扩大向量库代替效果测量。
3. **速度**：记录生成、检索、数据库提取、查询和验证的独立时间；先做相同硬件、并发=1、同协议的质量基线，再验证同快照数据库/编译/语义证据的内容身份缓存。保持验证覆盖，避免直接减检查来变快。

设计尚未完全实现的细粒度业务契约/约束到测试覆盖映射、项目地图缓存、人工澄清中断、跨项目补漏裁决和完整因子实验，保留为后续项。双引擎整体审计 P/R/F1 本次未重评，不能由单规则案例推断整个系统审计准确率提升。
