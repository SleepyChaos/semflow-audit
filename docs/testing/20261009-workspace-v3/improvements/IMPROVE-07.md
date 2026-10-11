# IMPROVE-07：复核覆盖、分页与绑定纠正

归档批次：`20261009-workspace-v3`。状态：历史改进。

## 项目改进边界

复核分页恢复、覆盖预算、小模块预读、源码条件与运行未知分离、符号绑定。

## 版本与对照

discovery-retest v1诊断/v2最终；最终Scout3/Review6。批次v2是本轮迭代，不能与Repair2混用。

## 结果使用口径

原候选池59/59已复核；新增支持4主根因。原CodeQL复用，新Scout独立报告。

该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-268c55995aa802a2` | [benchmark-data/experiments/discovery-retest-results.md](../../../../benchmark-data/experiments/discovery-retest-results.md) | VER-781f5f50e0f091fd, VER-c4885854e3668097 |
| `RES-4bbd545e70c58d76` | [benchmark-data/experiments/discovery-retest-summary.json](../../../../benchmark-data/experiments/discovery-retest-summary.json) | VER-781f5f50e0f091fd, VER-c4885854e3668097 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-43302af99c022af3` | `artifacts/research/discovery-retest/20261005-v1/config.json` | `781f5f50e0f0` | 缺失，沿用原文件声明 |
| `RES-9c9499055b06f3a7` | `artifacts/research/discovery-retest/20261005-v1/rv-dvna/paired-12-scored.json` | `726645f20c1c` | RES-43302af99c022af3 |
| `RES-0e95a154428488d0` | `artifacts/research/discovery-retest/20261005-v1/rv-dvna/paired-12.json` | `c0ccaf7db817` | RES-43302af99c022af3 |
| `RES-1fb86ac28a3f1d2b` | `artifacts/research/discovery-retest/20261005-v1/rv-flask/paired-12-scored.json` | `a921cb534254` | RES-43302af99c022af3 |
| `RES-2cab3e325d5bfd87` | `artifacts/research/discovery-retest/20261005-v1/rv-flask/paired-12.json` | `39498b99de8d` | RES-43302af99c022af3 |
| `RES-86f962e1d6715905` | `artifacts/research/discovery-retest/20261005-v1/summary.json` | `40185bf9d199` | RES-43302af99c022af3 |
| `RES-6ceabeec38fac821` | `artifacts/research/discovery-retest/20261005-v2/config.json` | `c4885854e366` | 缺失，沿用原文件声明 |
| `RES-95b3b1129998f6ae` | `artifacts/research/discovery-retest/20261005-v2/integrity.json` | `b658ac7dee50` | RES-6ceabeec38fac821 |
| `RES-74293cff7fedda9d` | `artifacts/research/discovery-retest/20261005-v2/rv-dvna/paired-12-scored.json` | `bd01463e6b35` | RES-6ceabeec38fac821 |
| `RES-a3af9e1e5ae05ccf` | `artifacts/research/discovery-retest/20261005-v2/rv-dvna/paired-12.json` | `30de7602c0ba` | RES-6ceabeec38fac821 |
| `RES-0a4330b052d2bda1` | `artifacts/research/discovery-retest/20261005-v2/rv-flask/paired-12-scored.json` | `a3e93aaf473e` | RES-6ceabeec38fac821 |
| `RES-548802dae01c8265` | `artifacts/research/discovery-retest/20261005-v2/rv-flask/paired-12.json` | `b43f537f19c7` | RES-6ceabeec38fac821 |
| `RES-24bc175f00d62c24` | `artifacts/research/discovery-retest/20261005-v2/summary.json` | `2ef59afeaa95` | RES-6ceabeec38fac821 |
