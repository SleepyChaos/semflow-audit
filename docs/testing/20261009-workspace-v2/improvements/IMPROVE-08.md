# IMPROVE-08：模板输入与业务检查覆盖

归档批次：`20261009-workspace-v2`。状态：历史组合版本。

## 项目改进边界

加入模板/配置输入、业务优先级和按安全属性的调查任务，补齐实际输入。

## 版本与对照

最终Scout5/Review7；v2粗筛+v3补读+v4/v5复审+v6单次补测，各配置哈希独立。

## 结果使用口径

24/31是组合支持结果，扩大输入/预算；新增EJS静态命中不算Agent独立收益。

该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-05bc47d83d6da6f5` | [benchmark-data/experiments/discovery-coverage-results.md](../../../../benchmark-data/experiments/discovery-coverage-results.md) | VER-20f30db893d053a4, VER-3976bd729805e3b4, VER-4428e89630b6463f, VER-73d88c65832190eb, VER-b32779e191f99e1b, VER-ecdefba3c045ad97 |
| `RES-883a240b4300bac9` | [benchmark-data/experiments/discovery-coverage-summary.json](../../../../benchmark-data/experiments/discovery-coverage-summary.json) | VER-20f30db893d053a4, VER-3976bd729805e3b4, VER-4428e89630b6463f, VER-73d88c65832190eb, VER-b32779e191f99e1b, VER-ecdefba3c045ad97 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-27b5dde029d8fd6d` | `artifacts/research/discovery-coverage/20261006-v1/config.json` | `20f30db893d0` | 缺失，沿用原文件声明 |
| `RES-cdd349ea2e5bccbb` | `artifacts/research/discovery-coverage/20261006-v1/inputs.json` | `f5140efa8552` | RES-27b5dde029d8fd6d |
| `RES-8500b1fe1b01c2cf` | `artifacts/research/discovery-coverage/20261006-v1/rv-flask/full-review.json` | `5f120c1fbffe` | RES-27b5dde029d8fd6d |
| `RES-1f7ed3cee2f9308c` | `artifacts/research/discovery-coverage/20261006-v1/static/rv-flask/result.json` | `51ba92b20e3c` | RES-27b5dde029d8fd6d |
| `RES-8cb0f057e325e7b8` | `artifacts/research/discovery-coverage/20261006-v1/summary.json` | `18669c0a7a34` | RES-27b5dde029d8fd6d |
| `RES-bf6c411c3923b7ec` | `artifacts/research/discovery-coverage/20261006-v2/config.json` | `ecdefba3c045` | 缺失，沿用原文件声明 |
| `RES-d75e029458803a70` | `artifacts/research/discovery-coverage/20261006-v2/inputs.json` | `06027d604800` | RES-bf6c411c3923b7ec |
| `RES-f06f44fc5754a520` | `artifacts/research/discovery-coverage/20261006-v2/rv-flask/full-review.json` | `9a63c28eaa39` | RES-bf6c411c3923b7ec |
| `RES-9520fe8118031bf3` | `artifacts/research/discovery-coverage/20261006-v2/static/rv-dvna/result.json` | `5c9fe7593930` | RES-bf6c411c3923b7ec |
| `RES-c3c62133656a80a4` | `artifacts/research/discovery-coverage/20261006-v2/static/rv-flask/result.json` | `51ba92b20e3c` | RES-bf6c411c3923b7ec |
| `RES-d327b4456169a97c` | `artifacts/research/discovery-coverage/20261006-v2/summary.json` | `4a9f09c12cbd` | RES-bf6c411c3923b7ec |
| `RES-d191ef22e9ec9b20` | `artifacts/research/discovery-coverage/20261006-v3/config.json` | `b32779e191f9` | 缺失，沿用原文件声明 |
| `RES-af620e5528b94ae5` | `artifacts/research/discovery-coverage/20261006-v3/integrity.json` | `1921635e4ac6` | RES-d191ef22e9ec9b20 |
| `RES-2962d19f0044218c` | `artifacts/research/discovery-coverage/20261006-v3/rv-dvna/full-review.json` | `92c739858c7b` | RES-d191ef22e9ec9b20 |
| `RES-ee57080f676e14a7` | `artifacts/research/discovery-coverage/20261006-v3/rv-flask/full-review.json` | `b60fdecca846` | RES-d191ef22e9ec9b20 |
| `RES-c98044fd0317e719` | `artifacts/research/discovery-coverage/20261006-v3/summary.json` | `98bd1d46ad01` | RES-d191ef22e9ec9b20 |
| `RES-f999a79edfded4ac` | `artifacts/research/discovery-coverage/20261006-v4/config.json` | `73d88c658321` | 缺失，沿用原文件声明 |
| `RES-0791498bd3109da2` | `artifacts/research/discovery-coverage/20261006-v4/rv-flask/full-review.json` | `382b43850ab6` | RES-f999a79edfded4ac |
| `RES-a8509beb283aac3b` | `artifacts/research/discovery-coverage/20261006-v4/summary.json` | `8877b59f68c1` | RES-f999a79edfded4ac |
| `RES-2afb53735bfebaa0` | `artifacts/research/discovery-coverage/20261006-v5/config.json` | `4428e89630b6` | 缺失，沿用原文件声明 |
| `RES-9d482f381cb5f6ec` | `artifacts/research/discovery-coverage/20261006-v5/integrity.json` | `bc66c06026ec` | RES-2afb53735bfebaa0 |
| `RES-5b6605a585bf8b87` | `artifacts/research/discovery-coverage/20261006-v5/root-adjudication.json` | `220dd1403369` | RES-2afb53735bfebaa0 |
| `RES-5add5f77ff90b564` | `artifacts/research/discovery-coverage/20261006-v5/rv-dvna/full-review.json` | `1c673bb95670` | RES-2afb53735bfebaa0 |
| `RES-f05754135dea45c9` | `artifacts/research/discovery-coverage/20261006-v5/rv-flask/full-review.json` | `382b43850ab6` | RES-2afb53735bfebaa0 |
| `RES-1759f3bc6da53189` | `artifacts/research/discovery-coverage/20261006-v5/summary.json` | `2eefa44ac724` | RES-2afb53735bfebaa0 |
| `RES-0f019ba239d6d6d9` | `artifacts/research/discovery-coverage/20261006-v6/config.json` | `3976bd729805` | 缺失，沿用原文件声明 |
| `RES-804815e16ac40678` | `artifacts/research/discovery-coverage/20261006-v6/integrity.json` | `eb27c294fe39` | RES-0f019ba239d6d6d9 |
| `RES-a2e14c49c0dc6a2b` | `artifacts/research/discovery-coverage/20261006-v6/root-adjudication.json` | `8cb638da90cd` | RES-0f019ba239d6d6d9 |
| `RES-d6cf60b0b8071009` | `artifacts/research/discovery-coverage/20261006-v6/summary.json` | `c39baad1d8cf` | RES-0f019ba239d6d6d9 |
