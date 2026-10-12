# IMPROVE-03：受限规格与模板化QL生成

归档批次：`20261009-workspace-v2`。状态：历史改进。

## 项目改进边界

规则生成范围收敛、官方模板、编译/开发反馈和动态查询缓存纠正。

## 版本与对照

rule-ablation/framework-ablation/dev-feedback；旧K受限规格作为后续比较基线，组别和Prompt仍依manifest。

## 结果使用口径

修正前动态缓存评估作废；修正后主实验和开发反馈分别保存。

该组是测试归档归属；VALIDATION 组只补充验证既有实现。旧版对照臂仍绑定其原版本，实际实现身份逐条查看同批配置和哈希收据。
[共享的归档时环境](../environment.json)只适用于当前源码快照；不能补填历史环境。

## 报告与机器汇总

| 结果 ID | 文件 | 相关内容版本收据 |
| --- | --- | --- |
| `RES-1cb67baa3385a3e5` | [docs/research/rule-generation-ablation-results.md](../../../../docs/research/rule-generation-ablation-results.md) | 仅声明或缺历史冻结，见登记册 |
| `RES-d8c1871f8662464a` | [docs/research/rule-generation-ablation-summary.json](../../../../docs/research/rule-generation-ablation-summary.json) | 仅声明或缺历史冻结，见登记册 |

## 原始结果与配置收据

完整 SHA-256、原字段及引用在[登记册](../registry.json)；原件与忽略目录中的冻结副本各保存一份。

| 结果 ID | 原文件 | SHA-256（前12位） | 同批配置/版本收据 ID |
| --- | --- | --- | --- |
| `RES-e2778d77cb6e118a` | `artifacts/benchmarks/dev-feedback-ablation-6c579229-399b-44a5-829d-055bcaf650d7/manifest.json` | `f91642636ea7` | 缺失，沿用原文件声明 |
| `RES-b895854d4aef1608` | `artifacts/benchmarks/dev-feedback-ablation-6c579229-399b-44a5-829d-055bcaf650d7/report.json` | `aeb81060246d` | RES-e2778d77cb6e118a |
| `RES-6ebc49ad941f764c` | `artifacts/benchmarks/dev-feedback-ablation-6c579229-399b-44a5-829d-055bcaf650d7/summary.json` | `a303b4ebe4c9` | RES-e2778d77cb6e118a |
| `RES-221b2818cc4bdf01` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/0ab2d6493f3c9e8422644d0d0bb6c412c9bd0ad469d0588cb2be433d3742f795/result.json` | `2b2a5dd8e7e6` | RES-513b4f8b095bb547 |
| `RES-bbec1350c18d732c` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/0abce1e1bab2cec9cc667075a25fff481ca192cafb4f1677832fbf69c6eac8ad/result.json` | `7806f9b11ba1` | RES-513b4f8b095bb547 |
| `RES-8962cacd2a5f51b0` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/0f8008752acde9d4ec0a9504156353104df6a09eb60e1668d0a9b0ca8d69033f/result.json` | `39ee6f338f78` | RES-513b4f8b095bb547 |
| `RES-e39470c0ba7debb7` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/1601a565569f6bdf5b04c4b9403a1bdf3ac8ac71b771d194bc3aa379a84572b3/result.json` | `c6834cd4e2e4` | RES-513b4f8b095bb547 |
| `RES-2e4edb0ea560fd2e` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/21af1b97580e473553684f1d4d0e4cb255eff5375d08056e950f8bcaf8cc8528/result.json` | `000a62664a7d` | RES-513b4f8b095bb547 |
| `RES-3d96d2129812b6b7` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/35ba57411539f22e39431304b5de24c2c6120eb7e2c1da6eaf8ccc64ab433af5/result.json` | `aac23dd4c0e6` | RES-513b4f8b095bb547 |
| `RES-f0148f58910103e1` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/5a1f0bb86d1853182512657f0f69cf56e185b8a7940567b6254013e084adaba2/result.json` | `fdcdd4b05462` | RES-513b4f8b095bb547 |
| `RES-d6a531e61d9c33e5` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/6c855ea4a6c946015b8e3a76dd226019222ab3f808c9c7bd84c363582c655187/result.json` | `4d17a11a4bfb` | RES-513b4f8b095bb547 |
| `RES-403cb2bab6d6152e` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/b2cbb3d1d849a7e9074faaed6fa7b401e0a14fab5178e60a580f9c3e6e59a4fc/result.json` | `beebcc2e5172` | RES-513b4f8b095bb547 |
| `RES-6b4e58a8063147e8` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/dev-evaluation/f5e0427b9eb9fb0ad24c8aeda394efb1ef589cddc55876194b4d896f91c22898/result.json` | `ae9568cd5955` | RES-513b4f8b095bb547 |
| `RES-513b4f8b095bb547` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/manifest.json` | `b81ef84c9204` | 缺失，沿用原文件声明 |
| `RES-8dc5b651c5723006` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/report.json` | `2005718ccf7c` | RES-513b4f8b095bb547 |
| `RES-bda9da24d5ca556b` | `artifacts/benchmarks/framework-ablation-2a29b068-9e95-453d-8e02-31b8172def2b/summary.json` | `e23dda927c37` | RES-513b4f8b095bb547 |
| `RES-903da7b456b307ea` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/03a7774926014981b18336ea36dc21b3792ac3bfd5ffefd035d99e23ddbc1af8/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-bd7ba3789604f603` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/04217d980f2475fabc5d73def1a377824461725891b682c1b31dcca6d331ae17/result.json` | `f89defa8c964` | RES-710e136e236f6763 |
| `RES-b680da7e5adb9501` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/06ce693fbb965fa4d5f3092c41f0d5acb8fe2ac13d12de2abd3b1a2061f97def/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-a80ecb689143a386` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/0754d26206e92ed13f1246a1c0411b372b047d98427a9328d424a09a1402db8e/result.json` | `fcf679b0de3c` | RES-710e136e236f6763 |
| `RES-4dc950b74e39bf99` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/0edb0bbf75bbc973ee89308764d2a6a0dac3315ee698fc1db2bd84de500e37d0/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-a9b2bba2e23b767f` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/113a7f0fc42de088da5b1b701d885abfbb9843c7b50adc98d6ee6ef92bc3b0ed/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-7ccdf74e53a7dcc0` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/13c26ceb300ff9d78d3420e6f5a6306e855bb8d012276163c82f38d52b60a705/result.json` | `cbd64bfc049f` | RES-710e136e236f6763 |
| `RES-ab229508fc4fd6d1` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/14691cc1b7774278e149b5ea76f7b9284f04f96d3c80916c2b56b12b3624d702/result.json` | `10b2a3d8e644` | RES-710e136e236f6763 |
| `RES-6c4261e5737042cd` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/171a302356c568d3b4f82fc16e1a46afeb7fa86f46db56e8271fd99c706adada/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-d3f9ddac9408ba48` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/204105b749dba01a1fe3c54911f72f46c906bb0f21542f913f90215f54c6ebf0/result.json` | `537c8939b788` | RES-710e136e236f6763 |
| `RES-457b302dc9ab557a` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/240c45a127966e1ae2aede3035f6038f7d6ddd587655be21bfe7e06bd3d0c6bd/result.json` | `b159db2f11da` | RES-710e136e236f6763 |
| `RES-7f39390e5f85399a` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/25a5fa4eac49ce07f94b121580aa522b26bcaff687f47957dcb0053c2455e182/result.json` | `569fe5c6b067` | RES-710e136e236f6763 |
| `RES-b749ac3c41f76b89` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/2c06225863aef5f18f71d30d63c637631b5b45c22adfd0d4c27e38c8c490b709/result.json` | `7a622b7b07e4` | RES-710e136e236f6763 |
| `RES-ffc7400492b6d672` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/2d2d354a594a6f8183ddd533145cdfcf4bd73a349c75aa73d56eb084c202ee5b/result.json` | `bb482ca296a9` | RES-710e136e236f6763 |
| `RES-5e6a0d1671cd6c3f` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/2e4e6efa9bdef815e627411284ab4d064eabe23dc650af52bc819e4c99c6b7c1/result.json` | `63da8583a33c` | RES-710e136e236f6763 |
| `RES-17d1b59964f66380` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/309d4f3ddb0e2782dbccdabad149a6a7f146c5d6cbc9ba636575d02dc0e2e646/result.json` | `6baf7e3fd299` | RES-710e136e236f6763 |
| `RES-a05f1f49f4dc3d05` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/3dce9fb14034e561f029a66d9f435fc179d4c0e468d813cde63c649bbcdc5f1c/result.json` | `f066c15e5a5c` | RES-710e136e236f6763 |
| `RES-03a08e885e565cf4` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/3eb6e07f3a85cfe4baaa78bcdcfc12f146645ac068defedcf1f00198fc8b9565/result.json` | `eac63498730a` | RES-710e136e236f6763 |
| `RES-52241aebbfcc6319` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/4231d172ea58e58169e19d8c85d0976104fbc45bb2647412765d2118d8e57739/result.json` | `5c105b895616` | RES-710e136e236f6763 |
| `RES-dfe070ca9c3a9059` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/4e46ea13d53939bbd3791c63216f722ca3d13ec4e8d01b9b68259c47f5c3f540/result.json` | `4cfc9e7aa43f` | RES-710e136e236f6763 |
| `RES-864057721784bb69` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/58205590a400e50844370f924772d798dce022cc63c75118341f7b5f52e6164b/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-4e042bd635c096c9` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/64d8d16187807de910acf2406caf8dfabd65a69d4f2c9c5d7e7c8c96c9d440b3/result.json` | `724a7f5301a7` | RES-710e136e236f6763 |
| `RES-2c66c414a815974d` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/655d69b024106207cb96fdb3c07760211e731389491e23cd99589422897dd6d5/result.json` | `600452fbc676` | RES-710e136e236f6763 |
| `RES-10bb579a85dc45da` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/672e17ee6c7586b632a897516e0e35f88cbb91c7c3bd37f6704a55f295eacb36/result.json` | `e84c55e7f644` | RES-710e136e236f6763 |
| `RES-ce6e4d32dba883e5` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/69da2d88799789c912dc18878ef9b6cc5bd8cd6f737bee0bfcce064ba3dd3f9c/result.json` | `ca4d92eccba0` | RES-710e136e236f6763 |
| `RES-63646d2e89092168` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/70643a9ea79b9cf3a111c43ddf23ef7082f4e18939d540dd07ccbf66940481ab/result.json` | `3ff04b9e4a46` | RES-710e136e236f6763 |
| `RES-e91dcdd4b1bd2f4e` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/77066c3a2b67bb8fd4c21f3a77873661914dbbb433a4b7a08c1d7eca9dca3e69/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-239640006cbd4c3a` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/7b21ab6f3d5dbb7dcdb1f5a29d54ea4b377e14a92e2683684ab0a0b95b99ad1a/result.json` | `e6b48ae12d1b` | RES-710e136e236f6763 |
| `RES-dd62f3726a50c4a4` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/7cfef67ca614b65c635eadf4d40cfc77a263962351cf5a73d5275731a0db15c8/result.json` | `06b1e385110f` | RES-710e136e236f6763 |
| `RES-df4e46f01c49a57a` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/7db19e51c24d80009d279282ec96f0b381080c686251f66acc4397677cfbc464/result.json` | `b51b129bf7e0` | RES-710e136e236f6763 |
| `RES-1797b00bf1b411fa` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/809da4a21c0ecad3ca337d0c2a6be4be23d53261a56129e71a53eb70dcbecf9f/result.json` | `b4bebdfffdbf` | RES-710e136e236f6763 |
| `RES-1282cba32273078f` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/8f5839554dcc87cd255c0176f8420bdc6482cd7ba7e9e8fcda03f1e1f3727c93/result.json` | `ab245102a29a` | RES-710e136e236f6763 |
| `RES-f1fd8731d8b707ee` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/90793ea0689335088d6b1b80ed3ac2e1e47fd132c3f49759ba97b6280ed4a0ce/result.json` | `c18053398ffc` | RES-710e136e236f6763 |
| `RES-a4331dc5eddf8cbe` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/9238a26715d70e0eb97536fe89fb3d054c2f284d6e97a6cbc190421dbc753409/result.json` | `5c8a4b260c34` | RES-710e136e236f6763 |
| `RES-4acc18a106d40c42` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/9609941e973804197ffd6d85952302310a4506ac954f3c72f7bd1260983cb811/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-536ae708259473a5` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/9669feab4a224298ab510f4e5ea0a598f5eb57ad52c5752a46f8ca866721d5d0/result.json` | `20be4de6a621` | RES-710e136e236f6763 |
| `RES-199c0112e381afc3` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/a008a0b411053bc41f30453d5cd65c9841f5efb996675a754a6da5759e64e8fa/result.json` | `65d7f9e02407` | RES-710e136e236f6763 |
| `RES-f2d9e17f7437a099` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/a0404a9243f72c339b50bfcfbb2371fc10de45a221a268e130b9c2c2e8f3ce07/result.json` | `133415419bed` | RES-710e136e236f6763 |
| `RES-feaf3eba040b0af0` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/a4db722cefcb89d3d61c26999e609feaf829652fd2d2b7e7c0b0a90507d1152a/result.json` | `1af74154cfb7` | RES-710e136e236f6763 |
| `RES-d7f49c356f31b14b` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/a5dfbe3f38dc21eca93ed51571b2da2f818152ae2ab77a3f0630f3d09d753ab7/result.json` | `b4eaca0f1f5a` | RES-710e136e236f6763 |
| `RES-1e648853475ad0b8` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/a842b988d216a5ab38d3838b718f93322f83ef04bdc7a69a87fd0fa0b7b2ad20/result.json` | `2f94129bc300` | RES-710e136e236f6763 |
| `RES-17ab18d1b8160623` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/afb26eb3eb82f5d17c696b475d758b637eca444037e75e0b3bd5213d0fd0be28/result.json` | `719eb6f2d2e0` | RES-710e136e236f6763 |
| `RES-3a1443383e9a23a7` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/b56c487f07124c7ce2ef7d562fcf880618438e9e6bc80e62ff831b120c05b916/result.json` | `938f6edd0727` | RES-710e136e236f6763 |
| `RES-e326653bf0889a37` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/b8f323797945be142c37d34e178e4d03dd85e3c1ca471eb13a1644ce37170976/result.json` | `93509ecd73ad` | RES-710e136e236f6763 |
| `RES-b9cd18a2ba6bfb4f` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/b9847b850f7a1b093866073f9801d8a522329b7e87b35cc696eba18e92a1b5ae/result.json` | `8d7c8af0f2d4` | RES-710e136e236f6763 |
| `RES-737fac084716e7f8` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/c48e5ed1fb2ef18846ed117f27a0fc6c4750a739b132a41d15b1f89fe47cc90e/result.json` | `91e7fad740fb` | RES-710e136e236f6763 |
| `RES-f888ca657e53379b` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/c5ad955606e6ab7733e918988dfe2a8ea9a07efc2a2a03751f3316c9c10f6a81/result.json` | `a9e269bdd211` | RES-710e136e236f6763 |
| `RES-e38f973a97df7529` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/c9041aaeee277efdd1cbcd87879351f02f1b3d4e3abdbc6d7af8a744a1f3d016/result.json` | `7fe62861f81f` | RES-710e136e236f6763 |
| `RES-4d7cb8389a3378e2` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/c9822f1b8c2522a3f9ecdbb91d80192740e82020a040a468b91e9fdd9e737c88/result.json` | `9deb337e4282` | RES-710e136e236f6763 |
| `RES-13bb8f6af5a391c4` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/d13481176079e752160eb8ee1f56fded335478c23fae8d3075878a2aebb37a82/result.json` | `f1bb84c9ce7e` | RES-710e136e236f6763 |
| `RES-9dfc0ac91800037a` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/d77270a4b6c3163e6a531c7c1319d9225d769ab828cfe581edffb23e6879da98/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-c5efaa90cc73c14e` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/d7d20c35c1ff54a01a08aabc4b5d1703cd8b1c110fa732303a07adef3dd296a6/result.json` | `dd9f6f4f952d` | RES-710e136e236f6763 |
| `RES-03a687e89106a10a` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/d895e161adb6741e6b67f3b3af6310624c50e9bf2e0b34440c46de4a4668657c/result.json` | `83b1fab3d590` | RES-710e136e236f6763 |
| `RES-d13127d5d9453736` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/d92a00e6464b4ac0a62f6e6f248c07535cb2b6b228c31cb016fdbed342508b06/result.json` | `7ef0adc4c39a` | RES-710e136e236f6763 |
| `RES-2c9e3ad21b5cd4e4` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/ddb2a1df06bcaf26ab95fe4cf539367970998973c29462e3883486b51d6aa404/result.json` | `70fd8fcb2c0b` | RES-710e136e236f6763 |
| `RES-b4a2e2f7706e4eb8` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/e0a00a210b6af927d782ebdba07b9782a430b74b3f19cd69d07ec25e9ecf0f69/result.json` | `a7d6450e5561` | RES-710e136e236f6763 |
| `RES-10d713b76a05ddda` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/e34240d7d383dc856910a206c7757bafcf9883047372c0a3db82d293fa124eae/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-c2501cf0f4fadea9` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/e6a73619bc8d1d3da052136c7f063ddfaf76bd643b93314148e672bddd74a3cc/result.json` | `d6a946106d5c` | RES-710e136e236f6763 |
| `RES-61d42eddbac6abc6` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/e6f5b02812181ea6275a261f80109d2417bb205ad3bd1dce49502b459b7efa2c/result.json` | `f99840fba5b1` | RES-710e136e236f6763 |
| `RES-df833bab1dd74a07` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/e882712fdfc89d61bbc14a5ba53fbfeccc36a8ed9bf7762bf9121301294c5539/result.json` | `d9a07b0f6529` | RES-710e136e236f6763 |
| `RES-5fbdff7108b19e0e` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/ee90f90f4f291e4b8f16d16e1d21803baa20f34e3632e0653800614a27c85660/result.json` | `257102609813` | RES-710e136e236f6763 |
| `RES-7f75de7ca2bdec7b` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/f311b605ff07f4c129e2c88255efd7337df071ba5c9756c3c2101d241ff4508a/result.json` | `037fa96f77fa` | RES-710e136e236f6763 |
| `RES-e394b3b8fa27f3dc` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/fc2be96a8bef7b9619489ab6becf5daf4ca7fa68c48d94a565cbfe6e38867e46/result.json` | `fdcdd4b05462` | RES-710e136e236f6763 |
| `RES-e2f9a3f13cbb2837` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/dev-evaluation/fc88f77e8c33a257e34c148dbc11f7617cfc7747f62f18caabcff60f52afe2f1/result.json` | `8a4019d43197` | RES-710e136e236f6763 |
| `RES-710e136e236f6763` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/manifest.json` | `ea6c1e33d9da` | 缺失，沿用原文件声明 |
| `RES-a447b56908aeff20` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/pre-cache-fix-report.json` | `e9f49c7e36a4` | RES-710e136e236f6763 |
| `RES-9ebff7dd37c6a224` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/report.json` | `2d0472060029` | RES-710e136e236f6763 |
| `RES-031b78e944f36c8d` | `artifacts/benchmarks/rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/summary.json` | `92ec13051311` | RES-710e136e236f6763 |
| `RES-c982406e58d83e2d` | `artifacts/dev-feedback-ablation.log` | `42b1169fbc13` | 缺失，沿用原文件声明 |
| `RES-3c17fd3dfae0c5e3` | `artifacts/dev-feedback-evaluation.log` | `eb3e60506c6f` | 缺失，沿用原文件声明 |
| `RES-c9ba08ae00f7dbd9` | `artifacts/framework-ablation-live.log` | `d9d0a7fcb810` | 缺失，沿用原文件声明 |
| `RES-45d77fddc662f661` | `artifacts/framework-devcheck-final.log` | `e3b0c44298fc` | 缺失，沿用原文件声明 |
| `RES-2232a464277b273d` | `artifacts/framework-devcheck.log` | `874b14d9ef54` | 缺失，沿用原文件声明 |
| `RES-2da212b62563bca6` | `artifacts/framework-evaluation-live.log` | `6ea003386f48` | 缺失，沿用原文件声明 |
| `RES-797b83d7d3a63b69` | `artifacts/framework-evaluation-replay.log` | `f4f8aacf6131` | 缺失，沿用原文件声明 |
| `RES-d825aba068d41213` | `artifacts/manual-model-baseline.log` | `213e8c9e99e4` | 缺失，沿用原文件声明 |
| `RES-5137cccbb09c2159` | `artifacts/rule-ablation-devcheck.log` | `91eec3a191f0` | 缺失，沿用原文件声明 |
| `RES-e1b58375607556e9` | `artifacts/rule-ablation-live.log` | `089a74d4f215` | 缺失，沿用原文件声明 |
| `RES-8c818bf78e3de858` | `artifacts/rule-ablation-resume.log` | `8a604b458685` | 缺失，沿用原文件声明 |
| `RES-15a89d051716296c` | `artifacts/rule-ablation-tests.log` | `e11119ec52c1` | 缺失，沿用原文件声明 |
| `RES-e382f1ab3f7a4178` | `artifacts/rule-cache-regression.log` | `2cd938ace546` | 缺失，沿用原文件声明 |
| `RES-640b05b50e780bf1` | `artifacts/rule-oracle-replay.log` | `6ccb56032042` | 缺失，沿用原文件声明 |
