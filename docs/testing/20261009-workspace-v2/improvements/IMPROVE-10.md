# IMPROVE-10：通用语义循环与当前默认版本

归档批次：`20261009-workspace-v2`。状态：当前默认能力归档。

## 项目改进边界

AST入口、条件化框架语义、业务政策/缺保护区分、最终值反证和分组独立复审。仓库迁移没有改变实现。

## 版本与对照

Scout7/Review9/Repair2/Rule8；OWASP48 revision-01是最终候选。当前源码WORKSPACE哈希另存；历史revision-01收据不能直接等同当前整个工作树。

## 结果使用口径

48例验收revision-01 TP18/FP2、P90%、R75%、F1 81.82%；开发集和验收集分开，已暴露仅作回归。迁移43项行为测试只是选定检查。

该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-1d8d4ff7b89d69ec` | [benchmark-data/experiments/owasp48-final-comparison.md](../../../../benchmark-data/experiments/owasp48-final-comparison.md) | VER-00c114fec3c04ed3, VER-13f80500222c61ec, VER-29172ba08c8c991c, VER-42ef805422916466, VER-5f4fde36ac120ce0, VER-9ac800364efc351e, VER-ac737dc72ee6a9e3, VER-af84d69b4941d779, VER-e2480ce206db92e5 |
| `RES-54b782bc90552dc5` | [benchmark-data/experiments/owasp48-final-summary.json](../../../../benchmark-data/experiments/owasp48-final-summary.json) | VER-00c114fec3c04ed3, VER-13f80500222c61ec, VER-29172ba08c8c991c, VER-42ef805422916466, VER-5f4fde36ac120ce0, VER-9ac800364efc351e, VER-ac737dc72ee6a9e3, VER-af84d69b4941d779, VER-e2480ce206db92e5 |
| `RES-04870fac120d0ae2` | [docs/workspace-migration-review.md](../../../../docs/workspace-migration-review.md) | 仅声明或缺历史冻结，见登记册 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-5930f32ec985b8a1` | `artifacts/competitors/ocr-build-receipt.json` | `10df19df5c9d` | 缺失，沿用原文件声明 |
| `RES-910ef9dee7afe96d` | `artifacts/research/owasp48/20261007-evolution/candidate-decision.json` | `8f1b5e6dd6cc` | RES-47627fd7581a3186 |
| `RES-411cfa664bd32534` | `artifacts/research/owasp48/20261007-evolution/comparators/bandit/acceptance-01/result.json` | `41f5462d2144` | RES-47627fd7581a3186 |
| `RES-55b84a08735f4cc3` | `artifacts/research/owasp48/20261007-evolution/comparators/bandit/development-01/result.json` | `cbc0104b701c` | RES-47627fd7581a3186 |
| `RES-6bcc56594f05265d` | `artifacts/research/owasp48/20261007-evolution/comparators/bandit/development-02/result.json` | `65216c156b47` | RES-47627fd7581a3186 |
| `RES-6e3ac1f887db1465` | `artifacts/research/owasp48/20261007-evolution/comparison-score-receipt.json` | `6faf20095c9e` | RES-47627fd7581a3186 |
| `RES-47627fd7581a3186` | `artifacts/research/owasp48/20261007-evolution/config.json` | `2060c47dea20` | 缺失，沿用原文件声明 |
| `RES-9f07e4d2bba96d94` | `artifacts/research/owasp48/20261007-evolution/inputs.json` | `b1a157d58438` | RES-47627fd7581a3186 |
| `RES-d43425a19dbd9d28` | `artifacts/research/owasp48/20261007-evolution/protocol.json` | `9a36948329a3` | RES-47627fd7581a3186 |
| `RES-db05332355f73376` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-01/review.json` | `9f2e47474252` | RES-cf55e770d297f537 |
| `RES-73813b71ed074ac7` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-01/scout.json` | `30d0cb5f9648` | RES-cf55e770d297f537 |
| `RES-0c4524b839c0afa6` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-01/summary.json` | `542471cff8ce` | RES-cf55e770d297f537 |
| `RES-ef4e08f8cc56c05d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-02/review.json` | `97bfc750c9c2` | RES-cf55e770d297f537 |
| `RES-e81c55743895b720` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-02/scout.json` | `e62b398dbfc5` | RES-cf55e770d297f537 |
| `RES-44f058c5ff118e70` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-02/summary.json` | `1c7e055e1011` | RES-cf55e770d297f537 |
| `RES-051b12d7839458fc` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-03/review.json` | `6fa1f1d571d3` | RES-cf55e770d297f537 |
| `RES-706a08bae9985fc3` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-03/scout.json` | `80e3d747f7bf` | RES-cf55e770d297f537 |
| `RES-c2caace9a044721d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-03/summary.json` | `157ad664cb8a` | RES-cf55e770d297f537 |
| `RES-81f3f9de0394aaf8` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-04/review.json` | `802c7835456b` | RES-cf55e770d297f537 |
| `RES-459d04b0b6c1567c` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-04/scout.json` | `bcf57b5b9d18` | RES-cf55e770d297f537 |
| `RES-c1124d28f3beeaff` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-04/summary.json` | `03404ff61cdb` | RES-cf55e770d297f537 |
| `RES-7f17d895e5c21b5f` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-05/review.json` | `22a44aa15671` | RES-cf55e770d297f537 |
| `RES-55c923e3cb04146c` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-05/scout.json` | `18a165d99296` | RES-cf55e770d297f537 |
| `RES-32b95fe3de71f9b8` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-05/summary.json` | `077fc109ab49` | RES-cf55e770d297f537 |
| `RES-27a31dd09aed24f8` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-06/review.json` | `75ab20771c9e` | RES-cf55e770d297f537 |
| `RES-320ee6492a1fef43` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-06/scout.json` | `41f87fa30f44` | RES-cf55e770d297f537 |
| `RES-03cc4b800ce5d697` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-06/summary.json` | `91f8c72a6f8d` | RES-cf55e770d297f537 |
| `RES-297081356e5bec12` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-07/review.json` | `972bf2fbaff3` | RES-cf55e770d297f537 |
| `RES-f57012a419cabdd6` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-07/scout.json` | `7c8d7c79f138` | RES-cf55e770d297f537 |
| `RES-9177204a46c974ec` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-07/summary.json` | `0ef596e124d9` | RES-cf55e770d297f537 |
| `RES-105d0184558bafb0` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-08/review.json` | `675474fed0e3` | RES-cf55e770d297f537 |
| `RES-fb02390276f4f9d4` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-08/scout.json` | `0e422803c83f` | RES-cf55e770d297f537 |
| `RES-84ddc8822778519c` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-08/summary.json` | `05a02be531f7` | RES-cf55e770d297f537 |
| `RES-b2f836fb0b1f2979` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-09/review.json` | `e8b2e50fde16` | RES-cf55e770d297f537 |
| `RES-78764553ae9ec4da` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-09/scout.json` | `c5995f45ca45` | RES-cf55e770d297f537 |
| `RES-d9c982d5aacdca91` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-09/summary.json` | `efbb49493bcb` | RES-cf55e770d297f537 |
| `RES-6ef6023d43727736` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-10/review.json` | `55ee6efd8cb2` | RES-cf55e770d297f537 |
| `RES-bd9ecfcf286724ab` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-10/scout.json` | `de4a41f08d44` | RES-cf55e770d297f537 |
| `RES-3dd2aa114be94ed9` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-10/summary.json` | `583b0f13e550` | RES-cf55e770d297f537 |
| `RES-9ef581f7b32701e4` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-11/review.json` | `903dd45397ac` | RES-cf55e770d297f537 |
| `RES-4d3edfb59a095494` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-11/scout.json` | `69af950506f9` | RES-cf55e770d297f537 |
| `RES-0cdac28b23e5db26` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-11/summary.json` | `3e16cb41864f` | RES-cf55e770d297f537 |
| `RES-46b934e881969fc6` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-12/review.json` | `2ebeb2eca877` | RES-cf55e770d297f537 |
| `RES-110a4c2747618904` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-12/scout.json` | `7059d8842a87` | RES-cf55e770d297f537 |
| `RES-2a9c34528dd7ff10` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/batch-12/summary.json` | `fa15dcd3a93f` | RES-cf55e770d297f537 |
| `RES-cf55e770d297f537` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/config.json` | `13f80500222c` | RES-47627fd7581a3186 |
| `RES-ddf2faeb3f2283fe` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/evaluation.json` | `4e435f69891e` | RES-cf55e770d297f537 |
| `RES-8f5978a3320a6515` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/integrity.json` | `e369ab2774cc` | RES-cf55e770d297f537 |
| `RES-3f58394c3048c761` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/acceptance-01/summary.json` | `ce6016f0216c` | RES-cf55e770d297f537 |
| `RES-1d2c9940835603ba` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-01/review.json` | `805d63b7cb66` | RES-519ee5143ae176d3 |
| `RES-e6725420fdb5f76c` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-01/scout.json` | `443bb230c819` | RES-519ee5143ae176d3 |
| `RES-b0791178de788371` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-01/summary.json` | `c5ccdf67e1b0` | RES-519ee5143ae176d3 |
| `RES-23e58b62b0f0051e` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-02/review.json` | `9754eaf44cd3` | RES-519ee5143ae176d3 |
| `RES-48223d385f659dad` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-02/scout.json` | `30696477d458` | RES-519ee5143ae176d3 |
| `RES-27217435eb9269b8` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-02/summary.json` | `8009cd7aec7e` | RES-519ee5143ae176d3 |
| `RES-e9cb25c3ca9fd156` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-03/review.json` | `41d6adff9736` | RES-519ee5143ae176d3 |
| `RES-214694c1e22b74a3` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-03/scout.json` | `18e1a88db656` | RES-519ee5143ae176d3 |
| `RES-f819dbd53fa91ec7` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-03/summary.json` | `68a7c07a16b4` | RES-519ee5143ae176d3 |
| `RES-2abf8f2373ca4667` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-04/review.json` | `eb68ec7c970b` | RES-519ee5143ae176d3 |
| `RES-e0494e5f93593481` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-04/scout.json` | `1423e77e7b33` | RES-519ee5143ae176d3 |
| `RES-834d9882ef151e10` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-04/summary.json` | `6a8014ac0597` | RES-519ee5143ae176d3 |
| `RES-69a923b14c0f795e` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-05/review.json` | `bfca5ebebd01` | RES-519ee5143ae176d3 |
| `RES-ceb453dfeb8433a6` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-05/scout.json` | `0161d6104336` | RES-519ee5143ae176d3 |
| `RES-f148686b95118813` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-05/summary.json` | `94e5aaa5b62d` | RES-519ee5143ae176d3 |
| `RES-dc22745420a630b1` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-06/review.json` | `d24d918a3ef6` | RES-519ee5143ae176d3 |
| `RES-ae9c2887af70f6cb` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-06/scout.json` | `f2466226dadf` | RES-519ee5143ae176d3 |
| `RES-82a964372e09c3a1` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-06/summary.json` | `b65d188f401a` | RES-519ee5143ae176d3 |
| `RES-dc698e5e7a71a9b9` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-07/review.json` | `84669dcd9288` | RES-519ee5143ae176d3 |
| `RES-8f26176643ddf961` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-07/scout.json` | `025c3eb2d6fa` | RES-519ee5143ae176d3 |
| `RES-eb48923fdaf0e44c` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-07/summary.json` | `6be9e24b4ac5` | RES-519ee5143ae176d3 |
| `RES-6c5365d762c1266d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-08/review.json` | `520e1f95d96e` | RES-519ee5143ae176d3 |
| `RES-372c395a93255d2e` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-08/scout.json` | `c10c432c0e42` | RES-519ee5143ae176d3 |
| `RES-181c0db81fd8b8f2` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-08/summary.json` | `439f7ce3fbda` | RES-519ee5143ae176d3 |
| `RES-dfb7e91ba615b990` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-09/review.json` | `25a9617f9fda` | RES-519ee5143ae176d3 |
| `RES-6a4e2d8a4cd85f91` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-09/scout.json` | `3a8c4538c437` | RES-519ee5143ae176d3 |
| `RES-e4d01b6f9439f9a2` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-09/summary.json` | `5d12bccb1101` | RES-519ee5143ae176d3 |
| `RES-ac70aa9cf7b82b11` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-10/review.json` | `0bb0bd8aa4ce` | RES-519ee5143ae176d3 |
| `RES-61b97b41bba64cfd` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-10/scout.json` | `f4d709eb9ffd` | RES-519ee5143ae176d3 |
| `RES-3c599258de015e07` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-10/summary.json` | `1936e234eda5` | RES-519ee5143ae176d3 |
| `RES-d2bb23a8c639d491` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-11/review.json` | `06ac027767c2` | RES-519ee5143ae176d3 |
| `RES-65d0cf1a88580bc7` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-11/scout.json` | `a992eab05b31` | RES-519ee5143ae176d3 |
| `RES-44376f0a48b6625c` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-11/summary.json` | `d772da55bddb` | RES-519ee5143ae176d3 |
| `RES-3da6f00701e7c79d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-12/review.json` | `feb0a8c02a63` | RES-519ee5143ae176d3 |
| `RES-517cc03cd548e174` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-12/scout.json` | `bd2e88132fc6` | RES-519ee5143ae176d3 |
| `RES-c888b1a65d65789b` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/batch-12/summary.json` | `60445dc9c87a` | RES-519ee5143ae176d3 |
| `RES-519ee5143ae176d3` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/config.json` | `5f4fde36ac12` | RES-47627fd7581a3186 |
| `RES-fa1a32e59ccd05cc` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/evaluation.json` | `f9943e442a78` | RES-519ee5143ae176d3 |
| `RES-4e4a1d67f99b8fb8` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/integrity.json` | `e369ab2774cc` | RES-519ee5143ae176d3 |
| `RES-88339b8062759b40` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-01/summary.json` | `7dde948a88f4` | RES-519ee5143ae176d3 |
| `RES-f83fd3d50deb7b45` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-01/review.json` | `cb99c16a350e` | RES-0b9116681bcd24e4 |
| `RES-d5f40da76b8df0d5` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-01/scout.json` | `fe8b58b425a5` | RES-0b9116681bcd24e4 |
| `RES-71739e4939da0390` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-01/summary.json` | `d26a37ded0d4` | RES-0b9116681bcd24e4 |
| `RES-d7f3e35ea485cdac` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-02/review.json` | `06d9881011f2` | RES-0b9116681bcd24e4 |
| `RES-b6ae3ea37c001d64` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-02/scout.json` | `e892906a758d` | RES-0b9116681bcd24e4 |
| `RES-a6307fe5450c6f07` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-02/summary.json` | `c0663462c8ca` | RES-0b9116681bcd24e4 |
| `RES-7d6c88c779842259` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-03/review.json` | `44ad3f22e337` | RES-0b9116681bcd24e4 |
| `RES-6ca36fae4e76ee55` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-03/scout.json` | `dbb7fec93a20` | RES-0b9116681bcd24e4 |
| `RES-0db2643446571ed7` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-03/summary.json` | `49f7a207ed11` | RES-0b9116681bcd24e4 |
| `RES-f97b031786c4b9ca` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-04/review.json` | `35710f46182d` | RES-0b9116681bcd24e4 |
| `RES-3efe2ffcf215b1d9` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-04/scout.json` | `f46bc7c05917` | RES-0b9116681bcd24e4 |
| `RES-8b46a5722e6a3965` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-04/summary.json` | `4e764f5495cf` | RES-0b9116681bcd24e4 |
| `RES-37300f46f61f9d66` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-05/review.json` | `fdb515a15161` | RES-0b9116681bcd24e4 |
| `RES-d2687df9e88dd89e` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-05/scout.json` | `935596d49053` | RES-0b9116681bcd24e4 |
| `RES-5acf0b8a3b609219` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-05/summary.json` | `d5e44b9ccdea` | RES-0b9116681bcd24e4 |
| `RES-db3b56e75c0ec16d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-06/review.json` | `06d1a25fea62` | RES-0b9116681bcd24e4 |
| `RES-2d7de1c950378e23` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-06/scout.json` | `bfdadcb06f87` | RES-0b9116681bcd24e4 |
| `RES-c3a43873482788b3` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-06/summary.json` | `2f926b4f5bf5` | RES-0b9116681bcd24e4 |
| `RES-4ba2ebdeebe4c3e9` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-07/review.json` | `7aa5825674b1` | RES-0b9116681bcd24e4 |
| `RES-56d57db5e0effebb` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-07/scout.json` | `7c7d53b09bfc` | RES-0b9116681bcd24e4 |
| `RES-9f50183d3388eff8` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-07/summary.json` | `fcc5b788bbe3` | RES-0b9116681bcd24e4 |
| `RES-f247f180d51fdf88` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-08/review.json` | `8c3b84fa7f47` | RES-0b9116681bcd24e4 |
| `RES-2eb3d705a4515ce2` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-08/scout.json` | `4c27b07c25b9` | RES-0b9116681bcd24e4 |
| `RES-d3f4d81da4dcd2b5` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-08/summary.json` | `76528bece178` | RES-0b9116681bcd24e4 |
| `RES-d824c1210cb26e31` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-09/review.json` | `cdd8372954a6` | RES-0b9116681bcd24e4 |
| `RES-4dd882ed22f5ebdd` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-09/scout.json` | `cada90e8759e` | RES-0b9116681bcd24e4 |
| `RES-1b817ee7f127e393` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-09/summary.json` | `803641dd1c73` | RES-0b9116681bcd24e4 |
| `RES-23a2ee81e50c7ac4` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-10/review.json` | `89b68d1773eb` | RES-0b9116681bcd24e4 |
| `RES-719dc60dccb361b5` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-10/scout.json` | `708af45eff41` | RES-0b9116681bcd24e4 |
| `RES-1a7fd5d6e9ad8ba6` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-10/summary.json` | `561b7ca006eb` | RES-0b9116681bcd24e4 |
| `RES-78887386ce870b5a` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-11/review.json` | `b5e2c7dbbdee` | RES-0b9116681bcd24e4 |
| `RES-85876c5cd5304235` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-11/scout.json` | `907fe310d280` | RES-0b9116681bcd24e4 |
| `RES-2b5488e9a0abdd45` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-11/summary.json` | `761b27651882` | RES-0b9116681bcd24e4 |
| `RES-ea2f38e726122213` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-12/review.json` | `099e7610b1e4` | RES-0b9116681bcd24e4 |
| `RES-fab29eee57269e5d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-12/scout.json` | `4de708113b24` | RES-0b9116681bcd24e4 |
| `RES-db0ee3772c426bec` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/batch-12/summary.json` | `eab532bdb87c` | RES-0b9116681bcd24e4 |
| `RES-0b9116681bcd24e4` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/config.json` | `e2480ce206db` | RES-47627fd7581a3186 |
| `RES-83a83b59457aa686` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/evaluation.json` | `7a45683bb4b0` | RES-0b9116681bcd24e4 |
| `RES-54ee31d95ef7732d` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/integrity.json` | `e369ab2774cc` | RES-0b9116681bcd24e4 |
| `RES-6060e09d6dff5ccd` | `artifacts/research/owasp48/20261007-evolution/runs/revision-01/development-02/summary.json` | `d4a0d1d3bd04` | RES-0b9116681bcd24e4 |
| `RES-869ad61f8a86a547` | `artifacts/research/owasp48/20261007-evolution/static/acceptance-01/result.json` | `f7a0c2ccfe58` | RES-47627fd7581a3186 |
| `RES-d6d2c08cc88996bf` | `artifacts/research/owasp48/20261007-evolution/static/development-01/result.json` | `5732b153bb2f` | RES-47627fd7581a3186 |
| `RES-e354973c7d6837a2` | `artifacts/research/owasp48/20261007-evolution/static/development-02/result.json` | `bdbbbafbb7fc` | RES-47627fd7581a3186 |
| `RES-a5ac391fba95ab60` | `artifacts/research/owasp48/20261007-evolution/versions/revision-01/identity.json` | `af84d69b4941` | RES-47627fd7581a3186 |
