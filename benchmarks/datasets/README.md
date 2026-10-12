# 测试数据归档

整理日期：2026-10-11。这里保存此前已收集的公开测试输入、固定源码、标签及既有去标签输入，不运行第三方程序，也不导入生产 RAG。

共 39 个压缩包、17,271 个成员文件，压缩后 126.7 MB。原盘点的 32 项材料候选继续见[功能测试分类](../test-programs/README.md)，压缩包数量不等于基准或通过数量。

## 验证与恢复

从仓库根目录运行：

```sh
python3 system/scripts/benchmarks/archive_research_materials.py
python3 system/scripts/benchmarks/archive_research_materials.py --restore
```

第一条校验包及所有成员的 SHA-256；第二条验证后恢复到 `benchmarks/raw/`、`evaluator-only/` 和 `model-inputs/`。已有不同内容时拒绝覆盖，不需要网络或安装额外依赖。对于已有本地原件的工作区，发布副本有凭据过滤，建议直接使用原件或在干净 checkout 中恢复。

## 压缩包目录

| 路径 | 文件数 | 压缩 MB |
| --- | ---: | ---: |
| [raw/discovery/crosscommit.tar.gz](raw/discovery/crosscommit.tar.gz) | 166 | 1.55 |
| [raw/discovery/eyeballvul.tar.gz](raw/discovery/eyeballvul.tar.gz) | 9 | 0.07 |
| [raw/discovery/openssf.tar.gz](raw/discovery/openssf.tar.gz) | 415 | 0.39 |
| [raw/discovery/owasp-python.tar.gz](raw/discovery/owasp-python.tar.gz) | 2,543 | 0.62 |
| [raw/discovery/realvuln.tar.gz](raw/discovery/realvuln.tar.gz) | 193 | 6.91 |
| [raw/discovery/sastbench.tar.gz](raw/discovery/sastbench.tar.gz) | 7 | 1.14 |
| [raw/discovery/secbenchjs.tar.gz](raw/discovery/secbenchjs.tar.gz) | 2,844 | 3.40 |
| [raw/discovery/secjs.tar.gz](raw/discovery/secjs.tar.gz) | 7 | 0.05 |
| [raw/discovery/vex-bench.tar.gz](raw/discovery/vex-bench.tar.gz) | 0 | 0.00 |
| [raw/discovery/vloc.tar.gz](raw/discovery/vloc.tar.gz) | 0 | 0.00 |
| [raw/discovery/vulngym.tar.gz](raw/discovery/vulngym.tar.gz) | 5 | 0.54 |
| [raw/discovery/standalone.tar.gz](raw/discovery/standalone.tar.gz) | 0 | 0.00 |
| [raw/rules/cqllm-slice-9e2abe0.tar.gz](raw/rules/cqllm-slice-9e2abe0.tar.gz) | 7 | 7.21 |
| [raw/rules/cwe-bench-java-spark.tar.gz](raw/rules/cwe-bench-java-spark.tar.gz) | 410 | 0.78 |
| [raw/rules/qlcoder-b879ac2.tar.gz](raw/rules/qlcoder-b879ac2.tar.gz) | 63 | 0.44 |
| [raw/rules/source-metadata.tar.gz](raw/rules/source-metadata.tar.gz) | 8 | 1.11 |
| [raw/rules/standalone.tar.gz](raw/rules/standalone.tar.gz) | 1 | 0.44 |
| [raw/repair/evaluator_only.tar.gz](raw/repair/evaluator_only.tar.gz) | 211 | 4.53 |
| [raw/project-pairs/pair-0881334be31562ed/post.tar.gz](raw/project-pairs/pair-0881334be31562ed/post.tar.gz) | 38 | 1.17 |
| [raw/project-pairs/pair-0881334be31562ed/pre.tar.gz](raw/project-pairs/pair-0881334be31562ed/pre.tar.gz) | 38 | 1.17 |
| [raw/project-pairs/pair-0881334be31562ed/standalone.tar.gz](raw/project-pairs/pair-0881334be31562ed/standalone.tar.gz) | 2 | 2.34 |
| [raw/project-pairs/pair-9d4a339b89e2beef/post.tar.gz](raw/project-pairs/pair-9d4a339b89e2beef/post.tar.gz) | 19 | 0.02 |
| [raw/project-pairs/pair-9d4a339b89e2beef/pre.tar.gz](raw/project-pairs/pair-9d4a339b89e2beef/pre.tar.gz) | 19 | 0.02 |
| [raw/project-pairs/pair-9d4a339b89e2beef/standalone.tar.gz](raw/project-pairs/pair-9d4a339b89e2beef/standalone.tar.gz) | 2 | 0.05 |
| [raw/project-pairs/pair-a0a4ebc7815b308f/post.tar.gz](raw/project-pairs/pair-a0a4ebc7815b308f/post.tar.gz) | 67 | 0.83 |
| [raw/project-pairs/pair-a0a4ebc7815b308f/pre.tar.gz](raw/project-pairs/pair-a0a4ebc7815b308f/pre.tar.gz) | 67 | 0.83 |
| [raw/project-pairs/pair-a0a4ebc7815b308f/standalone.tar.gz](raw/project-pairs/pair-a0a4ebc7815b308f/standalone.tar.gz) | 2 | 1.68 |
| [raw/project-pairs/pair-cd1928cf526399cd/post.tar.gz](raw/project-pairs/pair-cd1928cf526399cd/post.tar.gz) | 1,662 | 21.38 |
| [raw/project-pairs/pair-cd1928cf526399cd/pre.tar.gz](raw/project-pairs/pair-cd1928cf526399cd/pre.tar.gz) | 1,662 | 21.37 |
| [raw/project-pairs/pair-cd1928cf526399cd/standalone.tar.gz](raw/project-pairs/pair-cd1928cf526399cd/standalone.tar.gz) | 2 | 42.84 |
| [raw/project-pairs/pair-cefbcd4004c80277/post.tar.gz](raw/project-pairs/pair-cefbcd4004c80277/post.tar.gz) | 148 | 0.48 |
| [raw/project-pairs/pair-cefbcd4004c80277/pre.tar.gz](raw/project-pairs/pair-cefbcd4004c80277/pre.tar.gz) | 148 | 0.48 |
| [raw/project-pairs/pair-cefbcd4004c80277/standalone.tar.gz](raw/project-pairs/pair-cefbcd4004c80277/standalone.tar.gz) | 0 | 0.00 |
| [raw/project-pairs/pair-cff5121b5eadd458/post.tar.gz](raw/project-pairs/pair-cff5121b5eadd458/post.tar.gz) | 36 | 0.08 |
| [raw/project-pairs/pair-cff5121b5eadd458/pre.tar.gz](raw/project-pairs/pair-cff5121b5eadd458/pre.tar.gz) | 36 | 0.08 |
| [raw/project-pairs/pair-cff5121b5eadd458/standalone.tar.gz](raw/project-pairs/pair-cff5121b5eadd458/standalone.tar.gz) | 2 | 0.16 |
| [raw/project-pairs/standalone.tar.gz](raw/project-pairs/standalone.tar.gz) | 1 | 0.00 |
| [evaluator-only.tar.gz](evaluator-only.tar.gz) | 36 | 0.37 |
| [model-inputs.tar.gz](model-inputs.tar.gz) | 6,395 | 2.23 |

## 来源、边界和过滤

- [逐成员清单](../manifests/repository-datasets.json)：固定来源、版本、用途、上游许可、SHA-256、过滤与排除。
- [漏洞发现材料](../catalog/discovery.md)、[修复材料](../catalog/repair.md)、[规则生成材料](../catalog/rules.md)。
- [作者 README 与范围](../dataset-notes/README.md)、[正式评测协议](../evaluation-protocol.md)。

发布副本有 20 份文件移除了嵌入的测试凭据，保留任务记录及原件/发布版哈希；38 个路径因测试私钥、扫描产物、OS 元数据、符号链接或失败下载等原因排除。包含受限成员的原始传输包不发布，已展开的合格源码仍纳入对应包。排除记录保留失败状态；空的 rules/standalone 包表示其下载均失败，不表示有效数据。

PatchEval 任务 JSON 保留 1000 条任务；其中演示私钥已替换为标记。Forge 配对项目的一些密码学测试夹具也有替换，过滤副本无法用于要求原测试私钥的完整上游测试。所有修改均在发布副本完成，本地原件未改动。

包中的 `raw/` 和 `evaluator-only/` 含标签、作者规则、修复答案和 PoC。公开归档不等于允许把这些答案输入模型；实验仍需字段白名单、隐藏裁决和单独的模型输入。QLCoder/IRIS 的 Java/C 材料用于方法及专项参考，不代表当前 Python/JS 平台支持全部语言。

本次是材料归档与传输完整性验证；未补做模型评测、下载缺失运行镜像或改变历史成绩。
