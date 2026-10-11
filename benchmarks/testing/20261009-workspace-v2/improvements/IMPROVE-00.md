# IMPROVE-00：基础四阶段原型

归档批次：`20261009-workspace-v2`。状态：历史基线。

## 项目改进边界

初始任务隔离、静态扫描、AI复核、隔离修复、RAG规则与人工发布门。

## 版本与对照

早期原型与live-model批次；CodeQL和Prompt按原收据。没有完整工作树冻结，不作为今日源码版本。

## 结果使用口径

50项普通回归、真实链路集成与静态微基准分开；live-model失败完整保留。

该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-be9f3b9c52de162d` | [docs/research/benchmark-results.md](../../../../docs/research/benchmark-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-d082f41c994e2268` | [docs/research/benchmark-summary.json](../../../../docs/research/benchmark-summary.json) | 仅声明或缺历史冻结，见登记册 |
| `RES-d5657ed42e3457a2` | [docs/research/live-model-results.md](../../../../docs/research/live-model-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-158e957697bf17f4` | [docs/research/live-model-summary.json](../../../../docs/research/live-model-summary.json) | 仅声明或缺历史冻结，见登记册 |
| `RES-0aff1ee49f8e399d` | [docs/research/supplemental-benchmark-summary.json](../../../../docs/research/supplemental-benchmark-summary.json) | 仅声明或缺历史冻结，见登记册 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-5d18debe64945764` | `artifacts/bandit-benchmark-run.log` | `add8b6390908` | 缺失，沿用原文件声明 |
| `RES-62da3fb9b9849d11` | `artifacts/benchmark-run.log` | `da3f2b0986f2` | 缺失，沿用原文件声明 |
| `RES-8a849e2fca7fba4b` | `artifacts/benchmarks/e244a60d-c380-45da-9839-50c656acea03/bandit-report.json` | `80ada544d91f` | 缺失，沿用原文件声明 |
| `RES-d59fe9cd1e156d8e` | `artifacts/benchmarks/e244a60d-c380-45da-9839-50c656acea03/report.json` | `c2cdeee4958f` | 缺失，沿用原文件声明 |
| `RES-839eb136dfebedbd` | `artifacts/benchmarks/external-oracles-e9a88642-8b1c-40db-8d38-b266d40bc327/report.json` | `196b335c35a5` | 缺失，沿用原文件声明 |
| `RES-6a95ef1454115587` | `artifacts/benchmarks/live-model-859c5f0f-a059-4d79-acd5-6f00712628d9/report.json` | `0f5050603ee4` | 缺失，沿用原文件声明 |
| `RES-c88d49e25d1ffaec` | `artifacts/benchmarks/rag-23c029ef-6ca1-4441-b3fa-ad6c487dc0e3/report.json` | `6fe634e288a9` | 缺失，沿用原文件声明 |
| `RES-05c76d02596b67c8` | `artifacts/benchmarks/real-js-4818f4cc-78cd-451b-a306-26d6775873f3/report.json` | `1ef7624ae0b4` | 缺失，沿用原文件声明 |
| `RES-fe7a8c2f40058bb2` | `artifacts/benchmarks/rule-holdout-fb65636d-550f-404b-aa9c-eac34c3050e6/report.json` | `24a5598eeac2` | 缺失，沿用原文件声明 |
| `RES-a7c7a0edafcbfdb1` | `artifacts/external-oracles-run.log` | `b6ba999969c0` | 缺失，沿用原文件声明 |
| `RES-f8347620bcd67b71` | `artifacts/final-integration.log` | `d8d0d95d29cf` | 缺失，沿用原文件声明 |
| `RES-dc4a395de81d1b88` | `artifacts/js-validator-verification/report.json` | `4f4d6c0c871f` | 缺失，沿用原文件声明 |
| `RES-c129071fefbb293a` | `artifacts/live-followup-run.log` | `3ad6e8b412fe` | 缺失，沿用原文件声明 |
| `RES-bfd82468ff987f5e` | `artifacts/live-model-run.log` | `b945854930a1` | 缺失，沿用原文件声明 |
| `RES-83c716d5c0605903` | `artifacts/live-regression.log` | `2be79c797e50` | 缺失，沿用原文件声明 |
| `RES-c7adff1c944c35cc` | `artifacts/live-rule-validation.log` | `e311143c2821` | 缺失，沿用原文件声明 |
| `RES-a6860ed2edd4b227` | `artifacts/rag-benchmark-run.log` | `6a2b437fa01e` | 缺失，沿用原文件声明 |
| `RES-677540518983b65a` | `artifacts/real-cve-run.log` | `4fdbf2fe913f` | 缺失，沿用原文件声明 |
| `RES-c58f8a04330a53a6` | `artifacts/rule-holdout-run.log` | `a5d708fab6d2` | 缺失，沿用原文件声明 |
