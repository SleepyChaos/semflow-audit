# VALIDATION-10-CHAIN-COMPLETION：当前默认版本真实 Worker／浏览器链路补测

归档批次：`20261009-workspace-v3`。状态：部分执行，审批服务额度阻塞。

## 项目改进边界

真实 Chrome ZIP 上传、独立 Celery Worker、CodeQL＋Scout、Review9；两语言修复合同校准和全量可靠性；保留脚本失败与尚未评估的修复／规则／报告链路，未改生产代码。

## 版本与对照

20261009-chain-completion v1/v2 已执行；v3 仅准备恢复并做普通保障检查；Scout7/Review9/Repair2/Rule8；各 runner／输入／配置独立冻结。

## 结果使用口径

全量230项通过、3项新增归档保障通过；4个真实Scout＋2个Review完成，22调用；v1证据断言错误、v2定位错误保留；不能声明所有链路完成或通过。

该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-fd61bdf1b5a6e2dd` | [docs/research/chain-completion-20261009-plan.md](../../../../docs/research/chain-completion-20261009-plan.md) | VER-a4d982e7b33055c4 |
| `RES-3193e8d1d3be4c3a` | [docs/research/chain-completion-20261009-results.md](../../../../docs/research/chain-completion-20261009-results.md) | VER-a4d982e7b33055c4 |
| `RES-2483206da7012c31` | [docs/research/chain-completion-20261009-summary.json](../../../../docs/research/chain-completion-20261009-summary.json) | VER-a4d982e7b33055c4 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-d7a5ef9cbc40bcc1` | `artifacts/research/chain-completion/20261009-v1/17560558-3a86-4a04-9348-5516be8855bd-audit-receipt.json` | `4f12f27ae7af` | RES-b898d6b8d20c1b04 |
| `RES-59b27db8069238ed` | `artifacts/research/chain-completion/20261009-v1/36aed666-657c-4d1d-a3c8-ade2e7a0c2fe-completed-stage-receipt.json` | `829cb60c78d2` | RES-b898d6b8d20c1b04 |
| `RES-8d55e619403325f1` | `artifacts/research/chain-completion/20261009-v1/80a4dc44-1e4e-4ac2-baf7-67da6952b307-completed-stage-receipt.json` | `44513b797547` | RES-b898d6b8d20c1b04 |
| `RES-01f0d4279aca4a71` | `artifacts/research/chain-completion/20261009-v1/aa95c5f7-3636-4dd4-8edd-c68a51d46b72-completed-stage-receipt.json` | `e42b1ed7fc43` | RES-b898d6b8d20c1b04 |
| `RES-10bd977d585f73d3` | `artifacts/research/chain-completion/20261009-v1/api.log` | `e00c03396db9` | RES-b898d6b8d20c1b04 |
| `RES-a993e9849858a027` | `artifacts/research/chain-completion/20261009-v1/attempt-receipt.json` | `76ce989f22d1` | RES-b898d6b8d20c1b04 |
| `RES-ce0160e69cbbe457` | `artifacts/research/chain-completion/20261009-v1/ba9dc2fe-51d7-4d33-ad02-64ef67c9d40d-completed-stage-receipt.json` | `4d74eea1b01d` | RES-b898d6b8d20c1b04 |
| `RES-3a22715f2b275953` | `artifacts/research/chain-completion/20261009-v1/browser.log` | `bf37ad5d9593` | RES-b898d6b8d20c1b04 |
| `RES-b898d6b8d20c1b04` | `artifacts/research/chain-completion/20261009-v1/config.json` | `a4d982e7b330` | 缺失，沿用原文件声明 |
| `RES-adf35498010dd559` | `artifacts/research/chain-completion/20261009-v1/corpus-identity-receipt.json` | `1125956a88e6` | RES-b898d6b8d20c1b04 |
| `RES-6d88cd6b2b1f9d22` | `artifacts/research/chain-completion/20261009-v1/f9a6ae3c-aafd-4996-a280-cca9c9dbbaf2-audit-receipt.json` | `5bf841def5e9` | RES-b898d6b8d20c1b04 |
| `RES-f5f58b12b9aafcda` | `artifacts/research/chain-completion/20261009-v1/frontend.log` | `59daa11f6eb5` | RES-b898d6b8d20c1b04 |
| `RES-efeefbc86c37a20f` | `artifacts/research/chain-completion/20261009-v1/input-source.tar.gz` | `932380823108` | RES-b898d6b8d20c1b04 |
| `RES-38e73f8521ff944e` | `artifacts/research/chain-completion/20261009-v1/inputs/javascript/README.md` | `bc50fc3a35c1` | RES-b898d6b8d20c1b04 |
| `RES-7048a3be85bd4345` | `artifacts/research/chain-completion/20261009-v1/inputs/python/README.md` | `bc50fc3a35c1` | RES-b898d6b8d20c1b04 |
| `RES-a6cf3c8d4aa3a4cb` | `artifacts/research/chain-completion/20261009-v1/inputs.json` | `7453bf772062` | RES-b898d6b8d20c1b04 |
| `RES-8be1bf0d55b41795` | `artifacts/research/chain-completion/20261009-v1/javascript-baseline.sarif` | `a9353ce9ede6` | RES-b898d6b8d20c1b04 |
| `RES-3ce11b745f547dcb` | `artifacts/research/chain-completion/20261009-v1/javascript-source-evidence-and-confirmation-in-browser-failure.png` | `8ebfa58c9c07` | RES-b898d6b8d20c1b04 |
| `RES-cdd9a3a16be2d367` | `artifacts/research/chain-completion/20261009-v1/prepare.log` | `e3b0c44298fc` | RES-b898d6b8d20c1b04 |
| `RES-3b547ef570ab3547` | `artifacts/research/chain-completion/20261009-v1/progress.json` | `90d45a68fd1a` | RES-b898d6b8d20c1b04 |
| `RES-9acf33a2facd182e` | `artifacts/research/chain-completion/20261009-v1/python-baseline.sarif` | `b487ba3615f6` | RES-b898d6b8d20c1b04 |
| `RES-dd4f0a6aa23c972e` | `artifacts/research/chain-completion/20261009-v1/python-source-evidence-and-confirmation-in-browser-failure.png` | `5c57220f756c` | RES-b898d6b8d20c1b04 |
| `RES-6a0b3ba7cd5c0b34` | `artifacts/research/chain-completion/20261009-v1/regression/junit.xml` | `7803a7a99916` | RES-b898d6b8d20c1b04 |
| `RES-e5fecd9c9d5db16d` | `artifacts/research/chain-completion/20261009-v1/regression/pytest.log` | `fb6059e890fc` | RES-b898d6b8d20c1b04 |
| `RES-4c432355de1b5106` | `artifacts/research/chain-completion/20261009-v1/report.json` | `c7571b1b7d2b` | RES-b898d6b8d20c1b04 |
| `RES-2afa4cf5d1ffe569` | `artifacts/research/chain-completion/20261009-v1/runner-source.tar.gz` | `a430bb9b2951` | RES-b898d6b8d20c1b04 |
| `RES-ce3f89099a98cb2e` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/17560558-3a86-4a04-9348-5516be8855bd/execution.log` | `8d6bd785ef2f` | RES-b898d6b8d20c1b04 |
| `RES-00b944f5245e4be4` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/36aed666-657c-4d1d-a3c8-ade2e7a0c2fe/scout-map-receipt.json` | `470b2325651a` | RES-b898d6b8d20c1b04 |
| `RES-9a81a929db2ea733` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/36aed666-657c-4d1d-a3c8-ade2e7a0c2fe/units/0a6f7e06bb3cb9cdb89905b0/result.json` | `6852daa1eb5f` | RES-b898d6b8d20c1b04 |
| `RES-16e98bf903ca18f9` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/36aed666-657c-4d1d-a3c8-ade2e7a0c2fe/units/5a907b4d65939749fe5fd6ce/result.json` | `8d60f709cfb1` | RES-b898d6b8d20c1b04 |
| `RES-16c7b635a23dc49d` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/36aed666-657c-4d1d-a3c8-ade2e7a0c2fe/units/5d244ae7fa27715142dcc487/result.json` | `07338ff288a0` | RES-b898d6b8d20c1b04 |
| `RES-d34fd1090814680d` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/460720ab-cf84-4558-866d-34ff4d104fb3/execution.log` | `9b0e9ed57c6c` | RES-b898d6b8d20c1b04 |
| `RES-8825b64b31f9257a` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/80a4dc44-1e4e-4ac2-baf7-67da6952b307/batches/814b2157b21a981934577ef3/result.json` | `cf63c224f69f` | RES-b898d6b8d20c1b04 |
| `RES-34c20ec5f36b1f6e` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/80a4dc44-1e4e-4ac2-baf7-67da6952b307/batches/recovery-15f45803d8d8ad20d65796e4/result.json` | `da2388c1f89c` | RES-b898d6b8d20c1b04 |
| `RES-f1ff999d633555ad` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/80a4dc44-1e4e-4ac2-baf7-67da6952b307/batches/recovery-7c9c0a84306ce5e4fa8d74a6/result.json` | `782828f1ab4b` | RES-b898d6b8d20c1b04 |
| `RES-6b33da3f0fc5f1ec` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/80a4dc44-1e4e-4ac2-baf7-67da6952b307/batches/recovery-9a480c018edb045bfc92c872/result.json` | `8df41e4bd3d2` | RES-b898d6b8d20c1b04 |
| `RES-1d289a41f6b9b3fc` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/8e03dd16-a3cb-43b1-bdb0-6b3f1fe9de06/execution.log` | `b8e1437bd0eb` | RES-b898d6b8d20c1b04 |
| `RES-5a40db31a9975c21` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a319af4f-c711-4c54-91f3-2e2ccbf46675/scout-map-receipt.json` | `c4e2a7c7ab7b` | RES-b898d6b8d20c1b04 |
| `RES-6e71744693c28921` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a319af4f-c711-4c54-91f3-2e2ccbf46675/units/19cbd3970554c555d0165202/result.json` | `01cb3c6499ea` | RES-b898d6b8d20c1b04 |
| `RES-b967ec179ffd048c` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a319af4f-c711-4c54-91f3-2e2ccbf46675/units/24f0f1a66a6c5627746e6a7d/result.json` | `370b2491f290` | RES-b898d6b8d20c1b04 |
| `RES-567336708ae79ae6` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a319af4f-c711-4c54-91f3-2e2ccbf46675/units/456cae7479cb83d0fcb9664c/result.json` | `63d60b42defd` | RES-b898d6b8d20c1b04 |
| `RES-706b2a56c01eccdf` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a319af4f-c711-4c54-91f3-2e2ccbf46675/units/5b0f087bd0e7b024355961f3/result.json` | `7fe5d138375c` | RES-b898d6b8d20c1b04 |
| `RES-f8009ee7e5099d97` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a82f3f60-c615-4755-be1c-ecbee03d0764/scout-map-receipt.json` | `470b2325651a` | RES-b898d6b8d20c1b04 |
| `RES-82133845764bebf2` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a82f3f60-c615-4755-be1c-ecbee03d0764/units/0a6f7e06bb3cb9cdb89905b0/result.json` | `b8d1cf24d4ce` | RES-b898d6b8d20c1b04 |
| `RES-cb497d815128974d` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a82f3f60-c615-4755-be1c-ecbee03d0764/units/5a907b4d65939749fe5fd6ce/result.json` | `52e24c66498d` | RES-b898d6b8d20c1b04 |
| `RES-de55e3d247dfef7a` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/a82f3f60-c615-4755-be1c-ecbee03d0764/units/5d244ae7fa27715142dcc487/result.json` | `50fecff54ab8` | RES-b898d6b8d20c1b04 |
| `RES-4bdbb8e0a9353544` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/aa95c5f7-3636-4dd4-8edd-c68a51d46b72/batches/923c03d774f0fadf367fe13d/result.json` | `3205f11d7ff7` | RES-b898d6b8d20c1b04 |
| `RES-f4c524569eaa8094` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/aa95c5f7-3636-4dd4-8edd-c68a51d46b72/batches/recovery-547bf6878bb80574f552000c/result.json` | `9eaf52465d2f` | RES-b898d6b8d20c1b04 |
| `RES-127495c2cca1198e` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/aa95c5f7-3636-4dd4-8edd-c68a51d46b72/batches/recovery-8b8b3803806d1aa7835a9b08/result.json` | `e4b715f6662e` | RES-b898d6b8d20c1b04 |
| `RES-e4ecb141d08bb670` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/aa95c5f7-3636-4dd4-8edd-c68a51d46b72/batches/recovery-ec5c146c305c199fe8129ff2/result.json` | `df40aae9f556` | RES-b898d6b8d20c1b04 |
| `RES-1e671230e725d89b` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/ba9dc2fe-51d7-4d33-ad02-64ef67c9d40d/scout-map-receipt.json` | `c4e2a7c7ab7b` | RES-b898d6b8d20c1b04 |
| `RES-555a027491da5c29` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/ba9dc2fe-51d7-4d33-ad02-64ef67c9d40d/units/19cbd3970554c555d0165202/result.json` | `4c222dff56c2` | RES-b898d6b8d20c1b04 |
| `RES-964f832e12739c05` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/ba9dc2fe-51d7-4d33-ad02-64ef67c9d40d/units/24f0f1a66a6c5627746e6a7d/result.json` | `cac0d33e22e9` | RES-b898d6b8d20c1b04 |
| `RES-c9dfbf83bdb0cbc0` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/ba9dc2fe-51d7-4d33-ad02-64ef67c9d40d/units/456cae7479cb83d0fcb9664c/result.json` | `3bca0b24d75b` | RES-b898d6b8d20c1b04 |
| `RES-a2f32eb8e80d3ada` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/ba9dc2fe-51d7-4d33-ad02-64ef67c9d40d/units/5b0f087bd0e7b024355961f3/result.json` | `df06f04f5d43` | RES-b898d6b8d20c1b04 |
| `RES-9a2d67fd5e5b66ab` | `artifacts/research/chain-completion/20261009-v1/runtime/runs/f9a6ae3c-aafd-4996-a280-cca9c9dbbaf2/execution.log` | `1a86d734c361` | RES-b898d6b8d20c1b04 |
| `RES-2cbd44935ecd4fc8` | `artifacts/research/chain-completion/20261009-v1/worker.log` | `804edbf0dff7` | RES-b898d6b8d20c1b04 |
| `RES-581a6f5c719d517c` | `artifacts/research/chain-completion/20261009-v2/460720ab-cf84-4558-866d-34ff4d104fb3-audit-receipt.json` | `dc192532d105` | RES-098594ff3c1db247 |
| `RES-539335d33ec3db1e` | `artifacts/research/chain-completion/20261009-v2/8e03dd16-a3cb-43b1-bdb0-6b3f1fe9de06-audit-receipt.json` | `ab110a0626c2` | RES-098594ff3c1db247 |
| `RES-2b2a89f663bce10c` | `artifacts/research/chain-completion/20261009-v2/a319af4f-c711-4c54-91f3-2e2ccbf46675-completed-stage-receipt.json` | `857eaab6a138` | RES-098594ff3c1db247 |
| `RES-a462dfe74e9ba585` | `artifacts/research/chain-completion/20261009-v2/a82f3f60-c615-4755-be1c-ecbee03d0764-completed-stage-receipt.json` | `de4120c85144` | RES-098594ff3c1db247 |
| `RES-76c56d8e905216f2` | `artifacts/research/chain-completion/20261009-v2/attempt-receipt.json` | `a87bf1ab5fd2` | RES-098594ff3c1db247 |
| `RES-888368016ea2e9b5` | `artifacts/research/chain-completion/20261009-v2/browser.log` | `66f1d222b24f` | RES-098594ff3c1db247 |
| `RES-0eee922f639e96e0` | `artifacts/research/chain-completion/20261009-v2/calibration/javascript/original/oracle-result.json` | `c21dffa6cae0` | RES-098594ff3c1db247 |
| `RES-a3798f49c193f7ff` | `artifacts/research/chain-completion/20261009-v2/calibration/javascript/reference/oracle-result.json` | `15b5b002dd23` | RES-098594ff3c1db247 |
| `RES-eb2196a9e4dde633` | `artifacts/research/chain-completion/20261009-v2/calibration/python/original/oracle-result.json` | `6e19820c71a7` | RES-098594ff3c1db247 |
| `RES-411f7c3e9d0dbba1` | `artifacts/research/chain-completion/20261009-v2/calibration/python/reference/oracle-result.json` | `2d4993a943e3` | RES-098594ff3c1db247 |
| `RES-cb523e34d63e8a76` | `artifacts/research/chain-completion/20261009-v2/calibration/summary.json` | `a99b44549004` | RES-098594ff3c1db247 |
| `RES-098594ff3c1db247` | `artifacts/research/chain-completion/20261009-v2/config.json` | `ecdf42be7a2e` | 缺失，沿用原文件声明 |
| `RES-63507afa4e59a523` | `artifacts/research/chain-completion/20261009-v2/corpus-identity-receipt.json` | `1125956a88e6` | RES-098594ff3c1db247 |
| `RES-7c1ce3e7b678faa6` | `artifacts/research/chain-completion/20261009-v2/inputs.json` | `7453bf772062` | RES-098594ff3c1db247 |
| `RES-7b8e2031899acc96` | `artifacts/research/chain-completion/20261009-v2/javascript-browser-real-upload-codeql-scout-worker-join-failure.png` | `f0f27cc4e484` | RES-098594ff3c1db247 |
| `RES-ceefbda1943c9ce6` | `artifacts/research/chain-completion/20261009-v2/progress.json` | `0bd8d7cd9fd5` | RES-098594ff3c1db247 |
| `RES-882cfbf87ad85fed` | `artifacts/research/chain-completion/20261009-v2/python-browser-real-upload-codeql-scout-worker-join-failure.png` | `c6cadd18763b` | RES-098594ff3c1db247 |
| `RES-81f5b7fa6fcf7753` | `artifacts/research/chain-completion/20261009-v2/report.json` | `056a9f32a6e6` | RES-098594ff3c1db247 |
| `RES-f153ea3e17e4b1ad` | `artifacts/research/chain-completion/20261009-v2/runner-source.tar.gz` | `38a6855f0772` | RES-098594ff3c1db247 |
| `RES-9c3ddf781d525a98` | `artifacts/research/chain-completion/20261009-v3/archive-guards.log` | `abeece3d814b` | RES-e03fd097612384ed |
| `RES-c275da8d6b66590c` | `artifacts/research/chain-completion/20261009-v3/archive-guards.xml` | `042c133a466e` | RES-e03fd097612384ed |
| `RES-8d63ef599b74c691` | `artifacts/research/chain-completion/20261009-v3/attempt-receipt.json` | `602c64e64f69` | RES-e03fd097612384ed |
| `RES-19e9a4ba07e11cc2` | `artifacts/research/chain-completion/20261009-v3/closure-receipt.json` | `5d15d589ed0b` | RES-e03fd097612384ed |
| `RES-e03fd097612384ed` | `artifacts/research/chain-completion/20261009-v3/config.json` | `ddf753c5a5f2` | 缺失，沿用原文件声明 |
| `RES-0c7be83dae8e7028` | `artifacts/research/chain-completion/20261009-v3/corpus-identity-receipt.json` | `1125956a88e6` | RES-e03fd097612384ed |
| `RES-b5624b5dddcd6ec1` | `artifacts/research/chain-completion/20261009-v3/inputs.json` | `7453bf772062` | RES-e03fd097612384ed |
| `RES-87ea4218bb6ee4d4` | `artifacts/research/chain-completion/20261009-v3/runner-source.tar.gz` | `1cec0757ce62` | RES-e03fd097612384ed |
