# IMPROVE-06：双引擎发现与统一复核首版

归档批次：`20261009-workspace-v1`。状态：历史改进。

## 项目改进边界

CodeQL与独立Scout并发发现，保留分支失败/覆盖并统一复核。接入三链路首轮校准。

## 版本与对照

pipeline2，初始Scout1/Review4；dual-discovery多个诊断批与calibration-v1。校准同时对照旧/新修复、Rule8和静态工具，是混合测试。

## 结果使用口径

最终六自建样例支持正例1/3；校准中规则/修复未过正式准入，不称全部链路完成正式验收。

该组是本轮改进的测试归档归属。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-95783a579034a8f8` | [benchmark-data/experiments/calibration-results.md](../../../../benchmark-data/experiments/calibration-results.md) | VER-e54c560b74e98ea6 |
| `RES-6d0512d704d43486` | [benchmark-data/experiments/calibration-summary.json](../../../../benchmark-data/experiments/calibration-summary.json) | VER-e54c560b74e98ea6 |
| `RES-21856cd0c02abe44` | [benchmark-data/experiments/failure-analysis.md](../../../../benchmark-data/experiments/failure-analysis.md) | VER-e54c560b74e98ea6 |
| `RES-621bf0d575c95784` | [benchmark-data/experiments/owasp-upstream-comparison.md](../../../../benchmark-data/experiments/owasp-upstream-comparison.md) | VER-e54c560b74e98ea6 |
| `RES-82b1f18a310170cb` | [benchmark-data/experiments/repair-calibration-report.md](../../../../benchmark-data/experiments/repair-calibration-report.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-8ceaa59100cc51d4` | [docs/research/dual-engine-development-results.md](../../../../docs/research/dual-engine-development-results.md) | VER-0220319ad6b65b90, VER-186c4eb89f1a90ff, VER-22cea65fb7bc84f2, VER-24696fa4866dd3ab, VER-74e21d1263c22751, VER-78f42061e02adeb2, VER-839d3d9ad4490d94, VER-d07ee934c4403e21 |
| `RES-967084ba3feac96c` | [docs/research/dual-engine-development-summary.json](../../../../docs/research/dual-engine-development-summary.json) | VER-0220319ad6b65b90, VER-186c4eb89f1a90ff, VER-22cea65fb7bc84f2, VER-24696fa4866dd3ab, VER-74e21d1263c22751, VER-78f42061e02adeb2, VER-839d3d9ad4490d94, VER-d07ee934c4403e21 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-5010edef4afbfddc` | `artifacts/benchmarks/dual-discovery-20261005/protocol.json` | `74e21d1263c2` | 缺失，沿用原文件声明 |
| `RES-a97ecaa8868b9872` | `artifacts/benchmarks/dual-discovery-20261005/report.json` | `78f42061e02a` | 缺失，沿用原文件声明 |
| `RES-eff04e7fbf85f051` | `artifacts/benchmarks/dual-discovery-corrected-20261005/protocol.json` | `24696fa4866d` | 缺失，沿用原文件声明 |
| `RES-bb3709ca5e756781` | `artifacts/benchmarks/dual-discovery-corrected-20261005/report.json` | `839d3d9ad449` | 缺失，沿用原文件声明 |
| `RES-76c394cd3aea3331` | `artifacts/benchmarks/dual-discovery-entrypoints-20261005/protocol.json` | `d07ee934c440` | 缺失，沿用原文件声明 |
| `RES-e76c4ed561ca3031` | `artifacts/benchmarks/dual-discovery-entrypoints-20261005/report.json` | `22cea65fb7bc` | 缺失，沿用原文件声明 |
| `RES-18da7c16b7803355` | `artifacts/benchmarks/dual-discovery-final-20261005/protocol.json` | `0220319ad6b6` | 缺失，沿用原文件声明 |
| `RES-6b4838e3da656cee` | `artifacts/benchmarks/dual-discovery-final-20261005/report.json` | `186c4eb89f1a` | 缺失，沿用原文件声明 |
| `RES-c37a06ca8bd51242` | `artifacts/research/formal/20261005-calibration-v1/bandit/owasp-python/result.json` | `ffc600736ab5` | RES-6074f1735a451906 |
| `RES-5ecd9ebaa1d66921` | `artifacts/research/formal/20261005-calibration-v1/bandit/owasp-python-loader-fixed-py314/result.json` | `2eb0d40d4b47` | RES-6074f1735a451906 |
| `RES-a7279510dd79cde1` | `artifacts/research/formal/20261005-calibration-v1/bandit/owasp-python-py314/result.json` | `13451d3b0a8e` | RES-6074f1735a451906 |
| `RES-6074f1735a451906` | `artifacts/research/formal/20261005-calibration-v1/config.json` | `e54c560b74e9` | 缺失，沿用原文件声明 |
| `RES-a021852a84027bb0` | `artifacts/research/formal/20261005-calibration-v1/discovery/root-adjudication.json` | `26e44e323de9` | RES-6074f1735a451906 |
| `RES-3e678a32fcfb8568` | `artifacts/research/formal/20261005-calibration-v1/discovery/rv-dvna/pilot-summary.json` | `f4c0d4a28b40` | RES-6074f1735a451906 |
| `RES-6947321ed89e06be` | `artifacts/research/formal/20261005-calibration-v1/discovery/rv-flask/pilot-summary.json` | `afd286a84ae6` | RES-6074f1735a451906 |
| `RES-bf4c1cef427a272a` | `artifacts/research/formal/20261005-calibration-v1/inputs.json` | `33edc0abde3c` | RES-6074f1735a451906 |
| `RES-db031a18df817a20` | `artifacts/research/formal/20261005-calibration-v1/integrity.json` | `abb06a7ecf67` | RES-6074f1735a451906 |
| `RES-a0be5919b4602839` | `artifacts/research/formal/20261005-calibration-v1/loader-correction.json` | `383d1e182fc1` | RES-6074f1735a451906 |
| `RES-ce5db48813f66b9c` | `artifacts/research/formal/20261005-calibration-v1/posthoc/failure-analysis-receipt.json` | `c0047fbca42d` | RES-6074f1735a451906 |
| `RES-16d38480aa2433a4` | `artifacts/research/formal/20261005-calibration-v1/posthoc/repair-v2-round-2-existing-patch/full-result.json` | `176e9ce99cc6` | RES-6074f1735a451906 |
| `RES-9944384b0b1ecefc` | `artifacts/research/formal/20261005-calibration-v1/posthoc/repair-v2-round-2-existing-patch/oracle-result.json` | `86d1e0c6d10f` | RES-6074f1735a451906 |
| `RES-e2049856e76316a7` | `artifacts/research/formal/20261005-calibration-v1/repair/original-container-calibration/full-result.json` | `de217bd010a4` | RES-6074f1735a451906 |
| `RES-3a9302c88ae600d4` | `artifacts/research/formal/20261005-calibration-v1/repair/original-container-calibration/oracle-result.json` | `71bd62c055e6` | RES-6074f1735a451906 |
| `RES-e2a4444213472bf0` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-1/generation.json` | `be459dd0c712` | RES-6074f1735a451906 |
| `RES-700d8b09a7350769` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-1/hidden-evaluation/full-result.json` | `7123beb3d88b` | RES-6074f1735a451906 |
| `RES-372613f861a9690c` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-1/hidden-evaluation/oracle-result.json` | `86d1e0c6d10f` | RES-6074f1735a451906 |
| `RES-79318e2801950750` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-1/scored.json` | `d147c85d86f1` | RES-6074f1735a451906 |
| `RES-f5c25f57e60dc68d` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-2/generation.json` | `40002921aa6b` | RES-6074f1735a451906 |
| `RES-3e9b41ca8c048701` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-2/hidden-evaluation/full-result.json` | `929f4b2fa280` | RES-6074f1735a451906 |
| `RES-ee034eb24d703003` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-2/hidden-evaluation/oracle-result.json` | `86d1e0c6d10f` | RES-6074f1735a451906 |
| `RES-13de787f937620d4` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-2/scored.json` | `b3a5f84fd5a6` | RES-6074f1735a451906 |
| `RES-840462194f01fff1` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-3/generation.json` | `959067841c64` | RES-6074f1735a451906 |
| `RES-52f098586e3715e0` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-3/hidden-evaluation/full-result.json` | `62e274358b35` | RES-6074f1735a451906 |
| `RES-6cd31f7725788ba0` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-3/hidden-evaluation/oracle-result.json` | `86d1e0c6d10f` | RES-6074f1735a451906 |
| `RES-84d19b3a5aefe3d6` | `artifacts/research/formal/20261005-calibration-v1/repair/v1-round-3/scored.json` | `442fa18167f4` | RES-6074f1735a451906 |
| `RES-b2ffcd5f4b669748` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-1/generation.json` | `4979c207d5a8` | RES-6074f1735a451906 |
| `RES-530b477e7cc17389` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-1/scored.json` | `ca9c86990ebe` | RES-6074f1735a451906 |
| `RES-5edcb5cd6fdfb576` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-2/generation.json` | `5a56b83bfafe` | RES-6074f1735a451906 |
| `RES-f03d3a4304a1665f` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-2/scored.json` | `4608b16d525b` | RES-6074f1735a451906 |
| `RES-5c92a98b8c085eca` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-3/generation.json` | `cde21b98ba8c` | RES-6074f1735a451906 |
| `RES-4fe56ebb4cf4ee09` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-3/hidden-evaluation/full-result.json` | `29da78b0bab5` | RES-6074f1735a451906 |
| `RES-024799a98d93d0aa` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-3/hidden-evaluation/oracle-result.json` | `86d1e0c6d10f` | RES-6074f1735a451906 |
| `RES-d44e19e53ef7ca11` | `artifacts/research/formal/20261005-calibration-v1/repair/v2-round-3/scored.json` | `0f7ca5c09620` | RES-6074f1735a451906 |
| `RES-f3630b22b00eb1aa` | `artifacts/research/formal/20261005-calibration-v1/retrieval/summary.json` | `fb2e428717d7` | RES-6074f1735a451906 |
| `RES-111e803d79d4ae63` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/bm25-round-1/generation.json` | `c6fe7de65873` | RES-6074f1735a451906 |
| `RES-0e9f890d18ddc772` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/bm25-round-1/scored.json` | `c5d8666c5131` | RES-6074f1735a451906 |
| `RES-72bb3b0f623a21bb` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/bm25-round-2/generation.json` | `e6afee6ba620` | RES-6074f1735a451906 |
| `RES-1208f766d8a1cab9` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/bm25-round-2/scored.json` | `703a1eacda43` | RES-6074f1735a451906 |
| `RES-6c611755a0e037fc` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/bm25-round-3/generation.json` | `512ad22a4116` | RES-6074f1735a451906 |
| `RES-c31c12b0caa5feac` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/bm25-round-3/scored.json` | `316985559743` | RES-6074f1735a451906 |
| `RES-dce17ea781efc8e0` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/hybrid-round-1/generation.json` | `3f77addea30d` | RES-6074f1735a451906 |
| `RES-34a72eb7fbd6f45f` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/hybrid-round-1/scored.json` | `a87d4be15224` | RES-6074f1735a451906 |
| `RES-5bc53e7a91c7478d` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/hybrid-round-2/generation.json` | `167bb34ba39f` | RES-6074f1735a451906 |
| `RES-ba99172e6a094b8f` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/hybrid-round-2/scored.json` | `99eb9b03a005` | RES-6074f1735a451906 |
| `RES-99e7b7f0cdec96ab` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/hybrid-round-3/generation.json` | `d3bad9af0694` | RES-6074f1735a451906 |
| `RES-2f539b57d0b5caf8` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/hybrid-round-3/scored.json` | `8c23bfd181cd` | RES-6074f1735a451906 |
| `RES-8a5b1ed12cc20f71` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/vector-round-1/generation.json` | `c1974c68a3d4` | RES-6074f1735a451906 |
| `RES-ff0f6f84e07e164a` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/vector-round-1/scored.json` | `0d87584bb5b0` | RES-6074f1735a451906 |
| `RES-2c4e0652db0cfbfa` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/vector-round-2/generation.json` | `113f32a59a34` | RES-6074f1735a451906 |
| `RES-111b136e7dec6490` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/vector-round-2/scored.json` | `416bd03f23e6` | RES-6074f1735a451906 |
| `RES-498b5de33212b804` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/vector-round-3/generation.json` | `00e0f8c1978e` | RES-6074f1735a451906 |
| `RES-7a5940d80e0865f6` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-codeinj/vector-round-3/scored.json` | `1e3d729790d2` | RES-6074f1735a451906 |
| `RES-9ba2679cde3e441c` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/bm25-round-1/generation.json` | `e0a742fd509b` | RES-6074f1735a451906 |
| `RES-500ebffa8eaf8ff2` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/bm25-round-1/scored.json` | `6e3c8a3de962` | RES-6074f1735a451906 |
| `RES-bad20e2ed30964cb` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/bm25-round-2/generation.json` | `bf58d47ed764` | RES-6074f1735a451906 |
| `RES-9b57dc8436147368` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/bm25-round-2/scored.json` | `477543795725` | RES-6074f1735a451906 |
| `RES-cb30bcfaad15250a` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/bm25-round-3/generation.json` | `b570ee0f42fb` | RES-6074f1735a451906 |
| `RES-192a1a532cfe52d1` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/bm25-round-3/scored.json` | `47a58f815343` | RES-6074f1735a451906 |
| `RES-553302f4d9ebddc6` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/hybrid-round-1/generation.json` | `6b8cf3d4594f` | RES-6074f1735a451906 |
| `RES-ef7bca2cc5a0611e` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/hybrid-round-1/scored.json` | `baa58419dcaa` | RES-6074f1735a451906 |
| `RES-93ceb21dc803f7fd` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/hybrid-round-2/generation.json` | `8c224ecdad72` | RES-6074f1735a451906 |
| `RES-0433ae4be4f8f392` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/hybrid-round-2/scored.json` | `dab9d192012d` | RES-6074f1735a451906 |
| `RES-eec4f814802b2899` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/hybrid-round-3/generation.json` | `33c3443618ad` | RES-6074f1735a451906 |
| `RES-727d637819bdd467` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/hybrid-round-3/scored.json` | `61a7accb2b58` | RES-6074f1735a451906 |
| `RES-3f140b58649a1e2d` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/vector-round-1/generation.json` | `d53f58e3a375` | RES-6074f1735a451906 |
| `RES-81939454d618cbf7` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/vector-round-1/scored.json` | `d61cff76cff1` | RES-6074f1735a451906 |
| `RES-6ae5c5689c07841f` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/vector-round-2/generation.json` | `fbf4dd53c92b` | RES-6074f1735a451906 |
| `RES-2fcaba8f1d78625d` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/vector-round-2/scored.json` | `2a6caecf10a2` | RES-6074f1735a451906 |
| `RES-c4d6947592d44460` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/vector-round-3/generation.json` | `eda52507aa9a` | RES-6074f1735a451906 |
| `RES-c423bced8ab9ff98` | `artifacts/research/formal/20261005-calibration-v1/rules/ql-owasp-sqli/vector-round-3/scored.json` | `aa00fa109b54` | RES-6074f1735a451906 |
| `RES-b8e7d3337d2c5f66` | `artifacts/research/formal/20261005-calibration-v1/runner-snapshot/manifest.json` | `4c0baa2e0327` | RES-6074f1735a451906 |
| `RES-fa03a97eb1bc35a1` | `artifacts/research/formal/20261005-calibration-v1/static/owasp-python/result.json` | `b66b91d67c72` | RES-6074f1735a451906 |
| `RES-91b1ff2d1c56ab89` | `artifacts/research/formal/20261005-calibration-v1/static/owasp-python-loader-fixed/result.json` | `b1dbd1a2fe88` | RES-6074f1735a451906 |
| `RES-28b7d443821a6dd5` | `artifacts/research/formal/20261005-calibration-v1/static/pair-0881334be31562ed/result.json` | `152b5c7143f3` | RES-6074f1735a451906 |
| `RES-83d0bd07658909ff` | `artifacts/research/formal/20261005-calibration-v1/static/pair-9d4a339b89e2beef/result.json` | `0ec4b89b7460` | RES-6074f1735a451906 |
| `RES-de7ff0ea0925b384` | `artifacts/research/formal/20261005-calibration-v1/static/pair-a0a4ebc7815b308f/result.json` | `128f73f4bb55` | RES-6074f1735a451906 |
| `RES-140664375366c305` | `artifacts/research/formal/20261005-calibration-v1/static/pair-cd1928cf526399cd/result.json` | `63d81ad52d15` | RES-6074f1735a451906 |
| `RES-e3e47b5f76f7fb39` | `artifacts/research/formal/20261005-calibration-v1/static/pair-cefbcd4004c80277/result.json` | `b2108576db91` | RES-6074f1735a451906 |
| `RES-e68d2d20390fb9bd` | `artifacts/research/formal/20261005-calibration-v1/static/pair-cff5121b5eadd458/result.json` | `37bbdf0052e7` | RES-6074f1735a451906 |
| `RES-214d6cea701e6faf` | `artifacts/research/formal/20261005-calibration-v1/static/ql-owasp-codeinj/result.json` | `d554f4e44c1b` | RES-6074f1735a451906 |
| `RES-9d4d251068fdd4f0` | `artifacts/research/formal/20261005-calibration-v1/static/ql-owasp-sqli/result.json` | `ba1fcdc34ade` | RES-6074f1735a451906 |
| `RES-335009c3994409a2` | `artifacts/research/formal/20261005-calibration-v1/static/rv-dvna/result.json` | `486d898420c0` | RES-6074f1735a451906 |
| `RES-bbe002248557c20d` | `artifacts/research/formal/20261005-calibration-v1/static/rv-flask/result.json` | `649b38489261` | RES-6074f1735a451906 |
| `RES-4d184d419d545cef` | `artifacts/research/formal/20261005-calibration-v1/static-summary.json` | `702cbb367ec9` | RES-6074f1735a451906 |
| `RES-a986d80447182080` | `artifacts/research/formal/20261005-calibration-v1/summary.json` | `57367bbd9ad0` | RES-6074f1735a451906 |
| `RES-927ab2604eab2da0` | `artifacts/research/formal/20261005-calibration-v1/upstream-bearer-rescore.json` | `f5c3e4203726` | RES-6074f1735a451906 |
| `RES-bbbcbe4dd6737ef3` | `artifacts/research/formal-preparation/repair-calibration/oracle-script-receipt.json` | `fb8d72991185` | 缺失，沿用原文件声明 |
| `RES-96410dfb855be137` | `artifacts/research/formal-preparation/repair-calibration/source-receipt.json` | `0dafcb7a085f` | 缺失，沿用原文件声明 |
| `RES-90ca4eaf79a57e36` | `artifacts/research/worker-dual-reload-20261005.json` | `066b4cd7f1f0` | 缺失，沿用原文件声明 |
