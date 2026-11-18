# PR-1 与 PR-2 开发及测试报告

开发基线为本地个人分支的 `2a74e0a2b433745b23dd38fc2c5823c8df64174e`。该版本已有独立的 CodeQL 和 Scout 分支、Review v12、原有源码补证和跨执行续审。改动复用了这些入口。现状、边界和历史差异见 [改造前审计](review-evidence-current-state-20261119.md)，缓存流程、数据契约和实验入口见 [技术设计](review-evidence-design-20261119.md)。

## 修改清单

以下表中的实现文件和测试文件以 `system/` 为基准。

| 交付 | 主要变更文件 |
| --- | --- |
| PR-1 契约 | `contracts/src/semflow_contracts/` 下的 `review_handoff.py`、`discovery.py`、`schemas.py` |
| PR-1 产物生成和读取 | `research/src/semflow_research/` 下的 `runtime/review_report.py`、`runtime/discovery_outputs.py`、`runtime/discovery_merge.py`、`public/discovery_results.py` |
| PR-1 平台投影 | `backend/app/research_bridge/projection.py`，`candidate_review_attempts` 与已有候选状态一同返回 |
| PR-2 契约和恢复 | `contracts/src/semflow_contracts/` 下的 `review_memory.py`、`discovery.py`、`schemas.py`。 `research/src/semflow_research/` 下的 `runtime/review_memory.py`、`runtime/review_continuation.py`、`runtime/discovery_operations.py`、`public/review_continuation.py`、`public/discovery_results.py` |
| PR-2 操作入口 | `research_cli/src/semflow_cli/discovery_commands.py`、`frontend/src/features/ai-review/ReviewDetails.tsx` |
| 功能测试 | `research/tests/test_discovery_execution.py`、`research/tests/test_discovery_minimal_cli.py`、`tests/test_research_review_bridge.py` |

PR-1 把散落在评估结果和诊断轨迹中的逐候选状态发布成版本化报告。未评估、预算中断、输出被拒和证据不足均保留独立状态。PR-2 让缓存身份、旧引用、新证据和补证停因可查询，并提供同一候选的重读对照。Web 仍由原有路由调度，CLI 通过公共接口读取科研 ID。未引入迁移，已有结果在缺少新可选字段时仍可读取。

## 已执行验证

| 阶段 | 本机结果 |
| --- | --- |
| 开发前 | 定向回归 49 项通过 |
| PR-1 | 同组定向回归 49 项通过 |
| PR-2 | 定向回归 50 项通过，用时 56.46 秒 |
| 扩展回归 | 剔除依赖 PostgreSQL 的 `pipeline_context` 及真实工具集成项后，85 项通过，65 项未纳入，用时 60.57 秒 |
| 前端 | 定向 Biome 检查和 Vite 生产构建通过 |
| 历史读兼容 | 从已有 Flask 真实模型产物读取两份旧复审回执，保留原 `insufficient`。历史产物省略新增字段，读取没有触发模型调用。 |

从 `system/` 运行，依赖现有开发虚拟环境。平台测试使用隔离的 SQLite fixture，测试不连接生产服务。

```powershell
python -m pytest -q contracts/tests/test_contracts.py research/tests/test_review_handoff.py research/tests/test_discovery_execution.py research/tests/test_dual_discovery.py research/tests/test_discovery_minimal_cli.py tests/test_research_review_bridge.py
```

| 验证点 | 固定用例中的观察 |
| --- | --- |
| 合流与人工门 | CodeQL 和 Scout 产物保持独立来源。模型证据不足时平台候选仍为待人工处理。 |
| 两轮状态 | 科研测试保存首轮 `insufficient`，二轮取得范围内的新证据并输出 `supported`。测试查询两轮历史并核对旧记录保持原判断。 |
| 证据复用和重读 | 同一候选的续审复用一个源码页。无缓存方式重读同页，内容摘要一致，也能补取新证据。 |
| 已核对引文 | 工作台 API 集成测试使用 v12。配置一致时带入一项已核对源码引文的前提；模型配置改变时源码页仍命中，前提未命中并记录分析身份变化。 |
| 意义明确的停止 | 外部材料缺失时，平台拒绝发起续审。首轮已补读同一位置仍不足时保留人工定位动作；用例覆盖中断以及未调度。 |
| 重试 | 同一已完成的科研执行再次调用沿用执行回执；续审单独分配 ID。 |

首次扩展回归在 58 项通过后，停在旧的 `pipeline_context` 连接 PostgreSQL 的初始化步骤。本机缺少可用测试库，Docker 引擎未启动。第二次扩展回归排除该 fixture 和 integration 标记。

一次测试失败源于断言直接比较科研证据 ID 与平台投影 ID。修正后分别核对模型上下文与 API 投影，两端都验证前提指向各自的源码证据。无缓存路径和缓存路径使用相同候选和快照。

## 适用范围与后续

本轮固定用例使用测试替身验证编排、证据校验、版本兼容和状态转换。测试时长是本机回归耗时。没有发起真实模型调用，也未执行全量数据集、真实 CodeQL 或 Docker 集成实验。本轮无实际 Token 成本、精度、召回或延迟收益可报告。

下一阶段用冻结的真实小样本对比现行首轮、无缓存续审和缓存续审。用独立真值评分，记录各组新取证数量、未决恢复数量、错误结论、调用、Token 与耗时。再根据未决原因和证据缺口决定普及函数级事实缓存及跨函数按需导航的范围。
