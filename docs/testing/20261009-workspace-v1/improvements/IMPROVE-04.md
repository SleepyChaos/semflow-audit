# IMPROVE-04：语义修复与双集合RAG规则

归档批次：`20261009-workspace-v1`。状态：历史改进。

## 项目改进边界

修复语义解释/补证和双集合检索、源码理解、角色路由、有限候选。

## 版本与对照

repair1→2，rule2→6；semantic多批与legacy-rag匹配旧集复测。旧版对照不改标为新版本。

## 结果使用口径

单开发案例规则0/3→3/3；旧集v6仅1/18，旧K15/18。任务/预算分开；保留退化结果。

该组是本轮改进的测试归档归属。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-d25a834b9428809e` | [docs/research/legacy-rag-matched-results.md](../../../../docs/research/legacy-rag-matched-results.md) | VER-0bc3b83aa1caae2e, VER-6fadf4a5559b3b1c, VER-9022c6d6e4a79a0b, VER-9b27cfe9feeae284, VER-e5e823cbc87c0a6a |
| `RES-482e0dfdce466e19` | [docs/research/legacy-rag-matched-summary.json](../../../../docs/research/legacy-rag-matched-summary.json) | VER-0bc3b83aa1caae2e, VER-6fadf4a5559b3b1c, VER-9022c6d6e4a79a0b, VER-9b27cfe9feeae284, VER-e5e823cbc87c0a6a |
| `RES-a4a9f8ba06dbeeed` | [docs/research/semantic-development-results.md](../../../../docs/research/semantic-development-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-8bfafbd9946542d2` | [docs/research/semantic-development-summary.json](../../../../docs/research/semantic-development-summary.json) | 仅声明或缺历史冻结，见登记册 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-43017e168064aebf` | `artifacts/benchmarks/legacy-rag-deployed-20261004/manifest.json` | `0bc3b83aa1ca` | 缺失，沿用原文件声明 |
| `RES-cb97594391b24c3b` | `artifacts/benchmarks/legacy-rag-deployed-20261004/report.json` | `9022c6d6e4a7` | RES-43017e168064aebf |
| `RES-ab0bd3f97c9dc6a1` | `artifacts/benchmarks/legacy-rag-matched-20261004/manifest.json` | `9b27cfe9feea` | 缺失，沿用原文件声明 |
| `RES-e93baad9a4f3195d` | `artifacts/benchmarks/legacy-rag-matched-20261004/report.json` | `6fadf4a5559b` | RES-ab0bd3f97c9dc6a1 |
| `RES-3d74f5129c7c0d1e` | `artifacts/benchmarks/semantic-repair-20261004/report.json` | `25be500abaca` | 缺失，沿用原文件声明 |
| `RES-5add98cc269e985a` | `artifacts/benchmarks/semantic-repair-controlled-20261004/report.json` | `1d655d7a5b20` | 缺失，沿用原文件声明 |
| `RES-fbcb75a0f11ef21f` | `artifacts/benchmarks/semantic-rule-20261004/report.json` | `ccd637bc1432` | 缺失，沿用原文件声明 |
| `RES-d5e07bb54ada1e8e` | `artifacts/benchmarks/semantic-rule-bm25-20261004/report.json` | `547d33c1e6f8` | 缺失，沿用原文件声明 |
| `RES-653ff58cdb8c7fc7` | `artifacts/benchmarks/semantic-rule-controlled-20261004/report.json` | `e0d60ddecf08` | 缺失，沿用原文件声明 |
| `RES-ce1b9e57a03ccb7d` | `artifacts/benchmarks/semantic-rule-final-20261004/report.json` | `162ec44da1aa` | 缺失，沿用原文件声明 |
| `RES-f736f3a5ee48469e` | `artifacts/benchmarks/semantic-rule-final-verified-20261004/report.json` | `0364cfb45baa` | 缺失，沿用原文件声明 |
| `RES-6df4c260a6a49d51` | `artifacts/benchmarks/semantic-rule-refined-20261004/report.json` | `a04f667a55a9` | 缺失，沿用原文件声明 |
| `RES-9cff286f28e86b83` | `artifacts/benchmarks/semantic-rule-routed-20261004/report.json` | `06e3b856dc9e` | 缺失，沿用原文件声明 |
| `RES-d964f7a1ea287740` | `artifacts/benchmarks/semantic-rule-unrouted-20261004/report.json` | `663a7bf28da0` | 缺失，沿用原文件声明 |
| `RES-408f79c36e7daaca` | `artifacts/materials/rag-corpus-v2/manifest.json` | `acde007a5876` | 缺失，沿用原文件声明 |
| `RES-5b380be6d161bbcc` | `artifacts/research/embedding-discovery-2026-10-04.json` | `c969b1e53520` | 缺失，沿用原文件声明 |
| `RES-efacfe4c62a34cc2` | `artifacts/research/embedding-smoke-2026-10-04.json` | `6f41a0795cb0` | 缺失，沿用原文件声明 |
