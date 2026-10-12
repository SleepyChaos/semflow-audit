# IMPROVE-02：候选执行反馈与工作流测量

归档批次：`20261009-workspace-v1`。状态：历史改进。

## 项目改进边界

规则候选开发执行、可恢复反馈循环、节点时序与证据复用；Flask和真实项目配对接入。

## 版本与对照

实验rule5/review3；默认入口和实验分支不同。Flask baseline/live与real-pair各自独立批次。

## 结果使用口径

87项普通回归与集成另列；真实项目资源失败及补测保留。

该组是本轮改进的测试归档归属。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-a40e0c70a6fe156f` | [docs/research/phase-two-results.md](../../../../docs/research/phase-two-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-657adfddbe55be47` | [docs/research/phase-two-summary.json](../../../../docs/research/phase-two-summary.json) | 仅声明或缺历史冻结，见登记册 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-675f829718407fbd` | `artifacts/benchmarks/flask-baseline-56d72d5e-cb7c-41bb-a0ce-464b32ab55b2/report.json` | `b4a400b35071` | 缺失，沿用原文件声明 |
| `RES-44b77d5c748fb935` | `artifacts/benchmarks/flask-baseline-6d29470a-0090-454d-bb89-127d0870dd06/report.json` | `caf12ecf5d87` | 缺失，沿用原文件声明 |
| `RES-d5498aa84ab9db6b` | `artifacts/benchmarks/flask-live-a9f48831-e9cb-4055-8339-313e4fcdce3a/report.json` | `6fa1ec309374` | 缺失，沿用原文件声明 |
| `RES-05095d2d743a5fcf` | `artifacts/benchmarks/real-pair-pilot-ede5371c-6eb9-42c9-baeb-b3036301733e/report.json` | `720ae7032253` | 缺失，沿用原文件声明 |
| `RES-8bc32cb13f40ae38` | `artifacts/benchmarks/real-pair-pilot-ede5371c-6eb9-42c9-baeb-b3036301733e/resource-4096-1/report.json` | `f076c38980fa` | 缺失，沿用原文件声明 |
| `RES-83b3b82bf209a7f4` | `artifacts/phase-two-final-integration.log` | `3d3f747ed1c1` | 缺失，沿用原文件声明 |
| `RES-6bcc7627fe61f853` | `artifacts/phase-two-flask-baseline.log` | `b61353dff19c` | 缺失，沿用原文件声明 |
| `RES-0ef89074b313abd7` | `artifacts/phase-two-flask-live.log` | `8724dda882d4` | 缺失，沿用原文件声明 |
| `RES-3049bc681e8f56da` | `artifacts/phase-two-flask-runtime-install.log` | `78b7ab9335d7` | 缺失，沿用原文件声明 |
| `RES-f444a8f476a89cca` | `artifacts/phase-two-flask-runtime-oracle.log` | `593cfde3d873` | 缺失，沿用原文件声明 |
| `RES-7e60e3cdd4b09490` | `artifacts/phase-two-graph-tests.log` | `dedaa4f5b9e9` | 缺失，沿用原文件声明 |
| `RES-af7f8f2a2cec0fcc` | `artifacts/phase-two-integration.log` | `fd85a8b9b29e` | 缺失，沿用原文件声明 |
| `RES-73997a60d10ede73` | `artifacts/phase-two-real-materials-network-retry.log` | `d52ab5cb99ca` | 缺失，沿用原文件声明 |
| `RES-f0d425753357b94a` | `artifacts/phase-two-real-materials-resume.log` | `d1d6a62e8aff` | 缺失，沿用原文件声明 |
| `RES-d6e2583d1ff54bfd` | `artifacts/phase-two-real-materials.log` | `ba61d752c264` | 缺失，沿用原文件声明 |
| `RES-d462d5ac40d20f9f` | `artifacts/phase-two-real-pilot.log` | `42bcb80d1f2b` | 缺失，沿用原文件声明 |
| `RES-c1cc8d05cc2f60be` | `artifacts/phase-two-resource-followup.log` | `256b3ebdc61c` | 缺失，沿用原文件声明 |
| `RES-10c454809b91f0b1` | `artifacts/phase-two-selective-review.log` | `c431b724e022` | 缺失，沿用原文件声明 |
| `RES-a65ba167448dd3bc` | `artifacts/phase-two-synthesis-tests.log` | `1c59e9e37f04` | 缺失，沿用原文件声明 |
| `RES-90401036a2fa9d07` | `artifacts/phase-two-tests.log` | `66fa6e80a804` | 缺失，沿用原文件声明 |
