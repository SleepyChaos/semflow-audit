# IMPROVE-05：RAG规则稳定化与语料验证

归档批次：`20261009-workspace-v1`。状态：历史改进，Rule8沿用。

## 项目改进边界

上下文精简、阶段合同、进度纠正、有限source扩展；官方语料编译/开发验证与embedding索引。

## 版本与对照

rule7→8；rag-stabilization两批、v7/v8source对照、语料v3/v4分列。当前Rule8继承此能力，不重写历史测试身份。

## 结果使用口径

共同6000输出预算完整v8为15/18；旧K复用第一轮；8000预算source扩展另列。

该组是本轮改进的测试归档归属。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-f50d18891b67ae72` | [docs/research/rag-corpus-expansion-results.md](../../../../docs/research/rag-corpus-expansion-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-c28cf9876207c5cb` | [docs/research/rag-corpus-expansion-summary.json](../../../../docs/research/rag-corpus-expansion-summary.json) | 仅声明或缺历史冻结，见登记册 |
| `RES-f975df8ba1f294bd` | [docs/research/rag-corpus-expansion-v3-results.md](../../../../docs/research/rag-corpus-expansion-v3-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-801218f78f570cf5` | [docs/research/rag-corpus-expansion-v3-summary.json](../../../../docs/research/rag-corpus-expansion-v3-summary.json) | 仅声明或缺历史冻结，见登记册 |
| `RES-ae2a6047a8c6996b` | [docs/research/rag-stabilization-results.md](../../../../docs/research/rag-stabilization-results.md) | VER-0bc3b83aa1caae2e, VER-1ae36d2c4029a512, VER-286143e159dfd35c, VER-76cf8e623e743928, VER-dbc720480991481e, VER-f8a16ca588df9bc2 |
| `RES-dc95922dc3e7cbf9` | [docs/research/rag-stabilization-summary.json](../../../../docs/research/rag-stabilization-summary.json) | VER-0bc3b83aa1caae2e, VER-1ae36d2c4029a512, VER-286143e159dfd35c, VER-76cf8e623e743928, VER-dbc720480991481e, VER-f8a16ca588df9bc2 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-0d8d331c59043d55` | `artifacts/benchmarks/rag-stabilization-20261004/manifest.json` | `76cf8e623e74` | 缺失，沿用原文件声明 |
| `RES-1d68e16dda3a0c74` | `artifacts/benchmarks/rag-stabilization-20261004/report.json` | `1ae36d2c4029` | RES-0d8d331c59043d55 |
| `RES-a9ea0cd6b032c142` | `artifacts/benchmarks/rag-stabilization-v8-20261004/manifest.json` | `f8a16ca588df` | 缺失，沿用原文件声明 |
| `RES-b20f2ab1f9a5555e` | `artifacts/benchmarks/rag-stabilization-v8-20261004/report.json` | `286143e159df` | RES-a9ea0cd6b032c142 |
| `RES-393561c308f0b94e` | `artifacts/benchmarks/v7-external-source-development-20261004/report.json` | `6c12b23af7da` | 缺失，沿用原文件声明 |
| `RES-f9d28ac0e3d4ad7f` | `artifacts/benchmarks/v7-external-source-fixed-20261004/report.json` | `81743db6ea22` | 缺失，沿用原文件声明 |
| `RES-de679c03c2c86e08` | `artifacts/benchmarks/v7-source-extension-additional-20261004/report.json` | `268f4a0fa3b7` | 缺失，沿用原文件声明 |
| `RES-adf43e4f6e6b2391` | `artifacts/benchmarks/v8-external-source-20261004/report.json` | `b3de3b27fec5` | 缺失，沿用原文件声明 |
| `RES-8fb5ec33593b58ae` | `artifacts/benchmarks/v8-source-extension-additional-20261004/report.json` | `0fed7528ee21` | 缺失，沿用原文件声明 |
| `RES-537156048c24d531` | `artifacts/materials/rag-corpus-v3/manifest.json` | `775ffca04012` | 缺失，沿用原文件声明 |
| `RES-8c01a5e3913634a5` | `artifacts/materials/rag-corpus-v4/manifest.json` | `e162946eb6a1` | 缺失，沿用原文件声明 |
| `RES-5cf62684cf6b01b4` | `artifacts/research/corpus-coverage-v3.json` | `d986d0a41bd7` | 缺失，沿用原文件声明 |
| `RES-f6ce96ca00726e0f` | `artifacts/research/corpus-coverage-v4.json` | `b81e171f2761` | 缺失，沿用原文件声明 |
| `RES-72024632981a650a` | `artifacts/research/default-retrieval-v8-auto-20261004.json` | `bccb26108cb2` | 缺失，沿用原文件声明 |
| `RES-19ef4697f800c859` | `artifacts/research/default-retrieval-v8-initial-20261004.json` | `98133f8c7f71` | 缺失，沿用原文件声明 |
| `RES-61105340eed13544` | `artifacts/research/product-retrieval-v8-final-20261004.json` | `05ab95fcecfc` | 缺失，沿用原文件声明 |
| `RES-904363e1e2b4ea16` | `artifacts/research/product-retrieval-v8-initial-20261004.json` | `4b55fb1c44fe` | 缺失，沿用原文件声明 |
| `RES-ee50340d4ff8cbec` | `artifacts/research/product-slot-diagnosis-v8-20261004.json` | `0796d87a6992` | 缺失，沿用原文件声明 |
| `RES-9acc81a3f30d3c1b` | `artifacts/research/rag-inventory-after-expansion-20261004.json` | `f39e54626d7a` | 缺失，沿用原文件声明 |
| `RES-fee95162a6ba7820` | `artifacts/research/rag-inventory-before-expansion-20261004.json` | `ec0a046addbc` | 缺失，沿用原文件声明 |
| `RES-51bc9cefb706d7aa` | `artifacts/research/rag-inventory-v7-final-20261004.json` | `86d0976ab511` | 缺失，沿用原文件声明 |
| `RES-811370658441a89e` | `artifacts/research/rag-v8-postfreeze-deployment-delta.json` | `86c400223842` | 缺失，沿用原文件声明 |
| `RES-958be8de0d465202` | `artifacts/research/runtime-v8-health-20261004.json` | `9d3201e2f439` | 缺失，沿用原文件声明 |
| `RES-a5037dac9d2a98a3` | `artifacts/research/worker-v8-reload-20261004.json` | `ca4a774f00c7` | 缺失，沿用原文件声明 |
