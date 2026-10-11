# IMPROVE-09：语义判断与失败隔离

归档批次：`20261009-workspace-v1`。状态：历史组合版本/后续旧版对照。

## 项目改进边界

语义判断、来源引用、反证与失败隔离；历史样例及机制回放。

## 版本与对照

Scout6/Review8，discovery-semantics v1…v7；OWASP56。OWASP48的base冻结源码/旧平台对照也归此组，保留实际base配置。

## 结果使用口径

29/31是有效历史合并/补测；OWASP56不是全量1230AI。回放不是新未暴露端到端验收。

该组是本轮改进的测试归档归属。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-0f841b16a021c7fe` | [benchmark-data/experiments/discovery-generality-review.md](../../../../benchmark-data/experiments/discovery-generality-review.md) | VER-f3ac055fee5aff25 |
| `RES-5d43f4e9facb12b2` | [benchmark-data/experiments/discovery-generality-summary.json](../../../../benchmark-data/experiments/discovery-generality-summary.json) | 仅声明或缺历史冻结，见登记册 |
| `RES-cbecc187c7c5b853` | [benchmark-data/experiments/discovery-semantic-results.md](../../../../benchmark-data/experiments/discovery-semantic-results.md) | VER-04319df9fbaa2bbb, VER-57593101a089111f, VER-58f9a9da10eedbb2, VER-88dba3ef1d442fec, VER-b4b43b4ef3aa6e86, VER-b4da43d621f3b04e, VER-f02251b714af6895 |
| `RES-49bbddab5c9a08a3` | [benchmark-data/experiments/discovery-semantic-summary.json](../../../../benchmark-data/experiments/discovery-semantic-summary.json) | VER-04319df9fbaa2bbb, VER-57593101a089111f, VER-58f9a9da10eedbb2, VER-88dba3ef1d442fec, VER-b4b43b4ef3aa6e86, VER-b4da43d621f3b04e, VER-f02251b714af6895 |
| `RES-8908c87c5ac5ffde` | [benchmark-data/experiments/owasp-discovery-results.md](../../../../benchmark-data/experiments/owasp-discovery-results.md) | VER-51069a8db9dc1682 |
| `RES-1afe39ef5346585b` | [benchmark-data/experiments/owasp-discovery-summary.json](../../../../benchmark-data/experiments/owasp-discovery-summary.json) | VER-51069a8db9dc1682 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-70bd102c6e6e7f8d` | `artifacts/research/discovery-generalization/20261007-host-replay-v1/result.json` | `f3ac055fee5a` | 缺失，沿用原文件声明 |
| `RES-cd1d925d0a74ab45` | `artifacts/research/discovery-semantics/20261007-v1/config.json` | `f02251b714af` | 缺失，沿用原文件声明 |
| `RES-93f7c2974c70aa25` | `artifacts/research/discovery-semantics/20261007-v2/config.json` | `88dba3ef1d44` | 缺失，沿用原文件声明 |
| `RES-a10ca4a327c14769` | `artifacts/research/discovery-semantics/20261007-v2/summary.json` | `7fb41b41ca33` | RES-93f7c2974c70aa25 |
| `RES-533cf5e66f227b9f` | `artifacts/research/discovery-semantics/20261007-v3/config.json` | `58f9a9da10ee` | 缺失，沿用原文件声明 |
| `RES-d738b09c0c1c0335` | `artifacts/research/discovery-semantics/20261007-v3/integrity.json` | `b0a3982887c6` | RES-533cf5e66f227b9f |
| `RES-696ae684c51fffb2` | `artifacts/research/discovery-semantics/20261007-v3/root-adjudication.json` | `b3ea0ec51cec` | RES-533cf5e66f227b9f |
| `RES-fc6d096f6638d25b` | `artifacts/research/discovery-semantics/20261007-v3/summary.json` | `afa514da6caa` | RES-533cf5e66f227b9f |
| `RES-62e8a040e992ec84` | `artifacts/research/discovery-semantics/20261007-v4/config.json` | `b4da43d621f3` | 缺失，沿用原文件声明 |
| `RES-53d0c04e3a8d6c53` | `artifacts/research/discovery-semantics/20261007-v4/integrity.json` | `1ce6848b2f66` | RES-62e8a040e992ec84 |
| `RES-6b26129ff8d80c12` | `artifacts/research/discovery-semantics/20261007-v4/root-adjudication.json` | `8dbae63162e2` | RES-62e8a040e992ec84 |
| `RES-8e8e5cfed7b2c5ff` | `artifacts/research/discovery-semantics/20261007-v4/rv-dvna/selection.json` | `118ed98c2cb6` | RES-62e8a040e992ec84 |
| `RES-6cb6dc73b9a117e3` | `artifacts/research/discovery-semantics/20261007-v4/rv-dvna/targeted-scout.json` | `18e2cc88e003` | RES-62e8a040e992ec84 |
| `RES-bebdc2f4adc0d522` | `artifacts/research/discovery-semantics/20261007-v4/rv-flask/selection.json` | `8fc8af18dfdf` | RES-62e8a040e992ec84 |
| `RES-39bdd59f3dab039d` | `artifacts/research/discovery-semantics/20261007-v4/summary.json` | `daac14569492` | RES-62e8a040e992ec84 |
| `RES-b53b571dd6856897` | `artifacts/research/discovery-semantics/20261007-v5/config.json` | `b4b43b4ef3aa` | 缺失，沿用原文件声明 |
| `RES-d092a80bf0a64eb7` | `artifacts/research/discovery-semantics/20261007-v5/integrity.json` | `1ce6848b2f66` | RES-b53b571dd6856897 |
| `RES-b6222309cdfae20a` | `artifacts/research/discovery-semantics/20261007-v5/root-adjudication.json` | `d0535d9c507f` | RES-b53b571dd6856897 |
| `RES-efed93a928377d08` | `artifacts/research/discovery-semantics/20261007-v5/rv-dvna/selection.json` | `eb715a079d65` | RES-b53b571dd6856897 |
| `RES-ab174994a41b482c` | `artifacts/research/discovery-semantics/20261007-v5/rv-dvna/targeted-scout.json` | `285d31560f1d` | RES-b53b571dd6856897 |
| `RES-d4cdcb24c1ea009c` | `artifacts/research/discovery-semantics/20261007-v5/summary.json` | `6ebb1862e315` | RES-b53b571dd6856897 |
| `RES-52ca70158afb6dc6` | `artifacts/research/discovery-semantics/20261007-v6/config.json` | `57593101a089` | 缺失，沿用原文件声明 |
| `RES-4951c2b6862716d4` | `artifacts/research/discovery-semantics/20261007-v6/integrity.json` | `1ce6848b2f66` | RES-52ca70158afb6dc6 |
| `RES-a485b336de5c24af` | `artifacts/research/discovery-semantics/20261007-v6/rv-dvna/selection.json` | `4ca2156b3540` | RES-52ca70158afb6dc6 |
| `RES-dfbb573c33031909` | `artifacts/research/discovery-semantics/20261007-v6/rv-dvna/targeted-scout.json` | `7f0ae0a835e3` | RES-52ca70158afb6dc6 |
| `RES-433b11d5b77d9b49` | `artifacts/research/discovery-semantics/20261007-v6/summary.json` | `624fc847ea0e` | RES-52ca70158afb6dc6 |
| `RES-1bcbb26b975ec744` | `artifacts/research/discovery-semantics/20261007-v7/config.json` | `04319df9fbaa` | 缺失，沿用原文件声明 |
| `RES-4f84f475186e5d7a` | `artifacts/research/discovery-semantics/20261007-v7/integrity.json` | `1ce6848b2f66` | RES-1bcbb26b975ec744 |
| `RES-8896e3eccbd59857` | `artifacts/research/discovery-semantics/20261007-v7/root-adjudication.json` | `2c6c4e328b65` | RES-1bcbb26b975ec744 |
| `RES-72e00dd90d5c7d00` | `artifacts/research/discovery-semantics/20261007-v7/rv-dvna/selection.json` | `741fcd00c8c6` | RES-1bcbb26b975ec744 |
| `RES-2b18acc0080c5f61` | `artifacts/research/discovery-semantics/20261007-v7/rv-dvna/targeted-scout.json` | `c7e24c66d23b` | RES-1bcbb26b975ec744 |
| `RES-b46e9790a750393d` | `artifacts/research/discovery-semantics/20261007-v7/summary.json` | `88b608753010` | RES-1bcbb26b975ec744 |
| `RES-bad5810fef770ee4` | `artifacts/research/discovery-semantics/usage-ledger.json` | `90272f264d98` | 缺失，沿用原文件声明 |
| `RES-24f207dda47f5398` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-01/review.json` | `2ca152cdd670` | RES-2449f91124cb4934 |
| `RES-90bd4e09f33cd061` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-01/scout.json` | `4b32354c2c53` | RES-2449f91124cb4934 |
| `RES-2bd1efdad00a3990` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-01/summary.json` | `863309717ba5` | RES-2449f91124cb4934 |
| `RES-a03f45d719be278e` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-02/review.json` | `b0c884df7da0` | RES-2449f91124cb4934 |
| `RES-c23c17effac6ace1` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-02/scout.json` | `99a1d0c73709` | RES-2449f91124cb4934 |
| `RES-b03fd54c0fa84ff7` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-02/summary.json` | `3316031c9f34` | RES-2449f91124cb4934 |
| `RES-ac1fb73e852419ee` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-03/review.json` | `49022dfafefb` | RES-2449f91124cb4934 |
| `RES-28c786a3473ac71b` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-03/scout.json` | `ff7b684a6267` | RES-2449f91124cb4934 |
| `RES-302e721836f182c1` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-03/summary.json` | `6626da7ef235` | RES-2449f91124cb4934 |
| `RES-e891d7abeb135aac` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-04/review.json` | `7f72ba68a695` | RES-2449f91124cb4934 |
| `RES-cf272d188a142398` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-04/scout.json` | `524ef504896e` | RES-2449f91124cb4934 |
| `RES-2d4d81734674924d` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-04/summary.json` | `c991ddde348d` | RES-2449f91124cb4934 |
| `RES-67bf579e61c60eea` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-05/review.json` | `0115094094b0` | RES-2449f91124cb4934 |
| `RES-b5604e2dd5887619` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-05/scout.json` | `15ee25e06340` | RES-2449f91124cb4934 |
| `RES-f6d444a4c540310f` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-05/summary.json` | `727f13ec47b2` | RES-2449f91124cb4934 |
| `RES-fe59905fefd57501` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-06/review.json` | `fa9132cf9db1` | RES-2449f91124cb4934 |
| `RES-63a0cd2261f69ba8` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-06/scout.json` | `aff18908a91e` | RES-2449f91124cb4934 |
| `RES-ff0c9af75eb0d859` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-06/summary.json` | `ec2146339f88` | RES-2449f91124cb4934 |
| `RES-469d41229a395984` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-07/review.json` | `43c1d7266fb9` | RES-2449f91124cb4934 |
| `RES-1d445b0589115c94` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-07/scout.json` | `7bbfad736a22` | RES-2449f91124cb4934 |
| `RES-f2ac76dbdfe9baa7` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-07/summary.json` | `e030e349edda` | RES-2449f91124cb4934 |
| `RES-537c478b582c10fc` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-08/review.json` | `2779702d8701` | RES-2449f91124cb4934 |
| `RES-28eb40de974590d1` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-08/scout.json` | `1bd8ddf2f580` | RES-2449f91124cb4934 |
| `RES-05950952c7934ca5` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-08/summary.json` | `b0c47795c1e2` | RES-2449f91124cb4934 |
| `RES-d2f2950b61cc2c27` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-09/review.json` | `82b910f603b2` | RES-2449f91124cb4934 |
| `RES-19543f8c71a216b2` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-09/scout.json` | `c3ca436b5fc1` | RES-2449f91124cb4934 |
| `RES-49fcfdf127526a66` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-09/summary.json` | `5eeab6b619d7` | RES-2449f91124cb4934 |
| `RES-3ede87a0fbfbb9e1` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-10/review.json` | `a9d4cbe0a990` | RES-2449f91124cb4934 |
| `RES-4add06c5dd99e914` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-10/scout.json` | `430140352484` | RES-2449f91124cb4934 |
| `RES-9fea988f67d8c80e` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-10/summary.json` | `494de3681266` | RES-2449f91124cb4934 |
| `RES-0d7e272bf55c79da` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-11/review.json` | `bd805993ec3a` | RES-2449f91124cb4934 |
| `RES-41fd7c99cdeb925b` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-11/scout.json` | `9f9ce5ea3188` | RES-2449f91124cb4934 |
| `RES-325eac27b3be50a7` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-11/summary.json` | `e3df5874329c` | RES-2449f91124cb4934 |
| `RES-c8c68da4248009ef` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-12/review.json` | `a17db40fde8a` | RES-2449f91124cb4934 |
| `RES-c9962aeb5e101434` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-12/scout.json` | `56c189ebd097` | RES-2449f91124cb4934 |
| `RES-faac355096a769cf` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-12/summary.json` | `90e193e17841` | RES-2449f91124cb4934 |
| `RES-987f1acf837e3c74` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-13/review.json` | `6a9c626e7e04` | RES-2449f91124cb4934 |
| `RES-80787273b470b10e` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-13/scout.json` | `84771ab36e55` | RES-2449f91124cb4934 |
| `RES-4a0168fd2ab8afe2` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-13/summary.json` | `0a28f79904fe` | RES-2449f91124cb4934 |
| `RES-98c75bab093b2b9f` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-14/review.json` | `01b9be8a041d` | RES-2449f91124cb4934 |
| `RES-968db62844cb783f` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-14/scout.json` | `5f7e5d90db7d` | RES-2449f91124cb4934 |
| `RES-0868d305e5f7a2fd` | `artifacts/research/owasp-discovery/20261007-pilot-v1/batch-14/summary.json` | `fa7bf8283962` | RES-2449f91124cb4934 |
| `RES-2449f91124cb4934` | `artifacts/research/owasp-discovery/20261007-pilot-v1/config.json` | `51069a8db9dc` | 缺失，沿用原文件声明 |
| `RES-bef286832c673628` | `artifacts/research/owasp-discovery/20261007-pilot-v1/evaluation.json` | `d6a7a05e05b2` | RES-2449f91124cb4934 |
| `RES-cd844867d7e3b82d` | `artifacts/research/owasp-discovery/20261007-pilot-v1/integrity.json` | `cd3836000ebb` | RES-2449f91124cb4934 |
| `RES-cc8462f535d14d31` | `artifacts/research/owasp-discovery/20261007-pilot-v1/summary.json` | `8fab3e94abcf` | RES-2449f91124cb4934 |
| `RES-d1bc5cc3a793d562` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-01/review.json` | `29dde9723af2` | RES-c29b97a7a8e515aa |
| `RES-12675920aef71f35` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-01/scout.json` | `02a805bea5fe` | RES-c29b97a7a8e515aa |
| `RES-313011ba124eb545` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-01/summary.json` | `42c417fb9853` | RES-c29b97a7a8e515aa |
| `RES-79f9498ed4f2c8a4` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-02/review.json` | `a2e4ae3a9f7f` | RES-c29b97a7a8e515aa |
| `RES-b4b68f71ec4d30ee` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-02/scout.json` | `10942a6f57ac` | RES-c29b97a7a8e515aa |
| `RES-51a4d4b75ad26076` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-02/summary.json` | `c1366bb32502` | RES-c29b97a7a8e515aa |
| `RES-c16982bcda10fdb1` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-03/review.json` | `7a504a8872fc` | RES-c29b97a7a8e515aa |
| `RES-d30a5cad04c50c92` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-03/scout.json` | `ee9c5124e4e4` | RES-c29b97a7a8e515aa |
| `RES-8517b85d92f519ac` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-03/summary.json` | `17ce6a496655` | RES-c29b97a7a8e515aa |
| `RES-7acfe2228e47774b` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-04/review.json` | `4247e98bdeb9` | RES-c29b97a7a8e515aa |
| `RES-67bf499fac101050` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-04/scout.json` | `0aeff77c8c9e` | RES-c29b97a7a8e515aa |
| `RES-82c3d762f4dfde98` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-04/summary.json` | `1a96f6452ce8` | RES-c29b97a7a8e515aa |
| `RES-53f57d13b8719033` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-05/review.json` | `a4b1eb87e624` | RES-c29b97a7a8e515aa |
| `RES-73b8093b6ffcd3b8` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-05/scout.json` | `3bc6be646748` | RES-c29b97a7a8e515aa |
| `RES-dc172313c08ad307` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-05/summary.json` | `6dac4e02fb01` | RES-c29b97a7a8e515aa |
| `RES-8735346805f75953` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-06/review.json` | `1b9a5e46391c` | RES-c29b97a7a8e515aa |
| `RES-69ac3285f897355f` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-06/scout.json` | `75729ccf6ffa` | RES-c29b97a7a8e515aa |
| `RES-b3810d6a0f5da4b5` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-06/summary.json` | `f33b72750734` | RES-c29b97a7a8e515aa |
| `RES-09c378aafedb2799` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-07/review.json` | `8dc1e1d19bb0` | RES-c29b97a7a8e515aa |
| `RES-87ea8807874966cb` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-07/scout.json` | `6e4fc24badb0` | RES-c29b97a7a8e515aa |
| `RES-3032b9ca47d4a466` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-07/summary.json` | `09f08d4662e7` | RES-c29b97a7a8e515aa |
| `RES-f004ba170fd798f1` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-08/review.json` | `d41cb7394850` | RES-c29b97a7a8e515aa |
| `RES-f042d2325618dba3` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-08/scout.json` | `919e6d4ad70b` | RES-c29b97a7a8e515aa |
| `RES-43bf88211ecbc730` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-08/summary.json` | `4be70fbdeee9` | RES-c29b97a7a8e515aa |
| `RES-d8c604cb8cc64a4d` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-09/review.json` | `02bbec3bd79e` | RES-c29b97a7a8e515aa |
| `RES-8b5350d924fc3fe1` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-09/scout.json` | `f1478f6dc39e` | RES-c29b97a7a8e515aa |
| `RES-55b4c8dd813177a8` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-09/summary.json` | `de40c965742b` | RES-c29b97a7a8e515aa |
| `RES-7566fd960691537e` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-10/review.json` | `a2d89e466b23` | RES-c29b97a7a8e515aa |
| `RES-4a70e7523b494a69` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-10/scout.json` | `4fc69bff568d` | RES-c29b97a7a8e515aa |
| `RES-fbf16376b538d0d8` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-10/summary.json` | `d06b07c995a0` | RES-c29b97a7a8e515aa |
| `RES-6bcafeec90a05e9c` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-11/review.json` | `941f7462af98` | RES-c29b97a7a8e515aa |
| `RES-6581ef0b345ca380` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-11/scout.json` | `ecf082a4a6b8` | RES-c29b97a7a8e515aa |
| `RES-51d517f0a6eefa1f` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-11/summary.json` | `4dc73cf6e057` | RES-c29b97a7a8e515aa |
| `RES-d62b6cb082dec7aa` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-12/review.json` | `ddecd5e7734b` | RES-c29b97a7a8e515aa |
| `RES-fcb77155a4516d17` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-12/scout.json` | `c1dc5fd26823` | RES-c29b97a7a8e515aa |
| `RES-d61b071c61496f77` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/batch-12/summary.json` | `d53f04fd97b4` | RES-c29b97a7a8e515aa |
| `RES-c29b97a7a8e515aa` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/config.json` | `00c114fec3c0` | RES-47627fd7581a3186 |
| `RES-ff90d82775cb38d0` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/evaluation.json` | `3bb88a374d58` | RES-c29b97a7a8e515aa |
| `RES-a15da37d3ca88fe9` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/integrity.json` | `e369ab2774cc` | RES-c29b97a7a8e515aa |
| `RES-3a9b01e38ca6abee` | `artifacts/research/owasp48/20261007-evolution/runs/base/acceptance-01/summary.json` | `3c0ba2fd9493` | RES-c29b97a7a8e515aa |
| `RES-9af7c053dbdd9632` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-01/review.json` | `55955071ee95` | RES-43248d5206ce2150 |
| `RES-4ac66e07c0953a98` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-01/scout.json` | `3b0930f532af` | RES-43248d5206ce2150 |
| `RES-c93c3223be573eac` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-01/summary.json` | `5600180a2523` | RES-43248d5206ce2150 |
| `RES-3956d155625021d5` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-02/review.json` | `4000b482a71e` | RES-43248d5206ce2150 |
| `RES-e7ee07eeb66236b7` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-02/scout.json` | `0a85a1fe3cd5` | RES-43248d5206ce2150 |
| `RES-2f6c86621fc621b4` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-02/summary.json` | `9f90555b89ad` | RES-43248d5206ce2150 |
| `RES-13fe9ca1475b12e5` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-03/review.json` | `fd0724c40486` | RES-43248d5206ce2150 |
| `RES-f514b0564c82cca5` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-03/scout.json` | `45b1483e0f88` | RES-43248d5206ce2150 |
| `RES-42204c6c14cd280c` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-03/summary.json` | `df73e79269e3` | RES-43248d5206ce2150 |
| `RES-8b7fe5b8a8e3bc5c` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-04/review.json` | `e0181ea12ae4` | RES-43248d5206ce2150 |
| `RES-9f54db508747b3f7` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-04/scout.json` | `f11c2e4f903b` | RES-43248d5206ce2150 |
| `RES-d3d4f600ded29e31` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-04/summary.json` | `3774f02816fc` | RES-43248d5206ce2150 |
| `RES-77dea25bf0f31a4d` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-05/review.json` | `0dd3bc4e5f3f` | RES-43248d5206ce2150 |
| `RES-40d4f7f0f2eb47a0` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-05/scout.json` | `24642ee4b5f0` | RES-43248d5206ce2150 |
| `RES-04eb01ce812a39f5` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-05/summary.json` | `65f9f6fb32c8` | RES-43248d5206ce2150 |
| `RES-071f184a079345a4` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-06/review.json` | `84b14b0dde52` | RES-43248d5206ce2150 |
| `RES-a7de699542ffe713` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-06/scout.json` | `fd6412aadd8d` | RES-43248d5206ce2150 |
| `RES-3b7cba8911e5ac74` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-06/summary.json` | `498645950aa4` | RES-43248d5206ce2150 |
| `RES-bae793185867c9ae` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-07/review.json` | `73bae102eb0d` | RES-43248d5206ce2150 |
| `RES-bb93fa161700cc0c` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-07/scout.json` | `1434f1cc4ae6` | RES-43248d5206ce2150 |
| `RES-2cd085dafd787ea1` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-07/summary.json` | `8e783609ec90` | RES-43248d5206ce2150 |
| `RES-9764f0cac8d9dfed` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-08/review.json` | `5704b822630c` | RES-43248d5206ce2150 |
| `RES-8e2ae61f5181ad25` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-08/scout.json` | `1b1f3daa7bdf` | RES-43248d5206ce2150 |
| `RES-b27b197c5a96f709` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-08/summary.json` | `f5a647e45027` | RES-43248d5206ce2150 |
| `RES-5ae8ea8c859da4cb` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-09/review.json` | `f22fcd79bdc6` | RES-43248d5206ce2150 |
| `RES-1043408bf549e84b` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-09/scout.json` | `c204c73db14f` | RES-43248d5206ce2150 |
| `RES-c2f15fdf43da4ebc` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-09/summary.json` | `a274db1e450f` | RES-43248d5206ce2150 |
| `RES-03810dbd7cb13936` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-10/review.json` | `1efd4331fe5f` | RES-43248d5206ce2150 |
| `RES-cb39fd06fedba8a3` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-10/scout.json` | `85a70d67e88b` | RES-43248d5206ce2150 |
| `RES-b422e62076b9eed8` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-10/summary.json` | `165012dd71a1` | RES-43248d5206ce2150 |
| `RES-51d126ef3b558bfc` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-11/review.json` | `5fc59cb7cfb3` | RES-43248d5206ce2150 |
| `RES-3f1da76d6d863fa1` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-11/scout.json` | `1ab0fe75fa01` | RES-43248d5206ce2150 |
| `RES-0abe5d042c284698` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-11/summary.json` | `bcc4570ad4a2` | RES-43248d5206ce2150 |
| `RES-9524cc02665da644` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-12/review.json` | `f2ff892dcd6c` | RES-43248d5206ce2150 |
| `RES-2c6ee8c6eb1abb66` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-12/scout.json` | `1ac02a852d69` | RES-43248d5206ce2150 |
| `RES-de09231af7106cb4` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/batch-12/summary.json` | `8bd1ac7a89ea` | RES-43248d5206ce2150 |
| `RES-43248d5206ce2150` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/config.json` | `9ac800364efc` | RES-47627fd7581a3186 |
| `RES-84d13b4bd38d8eae` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/evaluation.json` | `897e8128fac7` | RES-43248d5206ce2150 |
| `RES-bc79ef9e7c09a20a` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/integrity.json` | `e369ab2774cc` | RES-43248d5206ce2150 |
| `RES-c081f9cc03cfba2f` | `artifacts/research/owasp48/20261007-evolution/runs/base/development-01/summary.json` | `6e38c7a344cb` | RES-43248d5206ce2150 |
| `RES-8787b2333b101079` | `artifacts/research/owasp48/20261007-evolution/versions/base/identity.json` | `ac737dc72ee6` | RES-47627fd7581a3186 |
