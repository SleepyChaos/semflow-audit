# 三类功能测试的统一入口

更新：2026-10-11。当前分类采用 **功能 → 测试意图 → 测试材料类型** 三级结构，详细归属见[三级功能分类 v2](classification-draft-v2.md)。

| 一级：功能 | 二级：测试意图示例 | 三级：材料类型 |
| --- | --- | --- |
| 双引擎代码审计 | 准确性、业务语义/定位、误报控制、覆盖/失败、耗时成本、产品链路 | 项目测试、专项测试集测试、工程流程用例测试 |
| 代码修复 | 安全有效性、业务保持、跨项目泛化、修改范围、失败恢复、补丁接受 | 项目测试、专项测试集测试、工程流程用例测试 |
| 规则生成 | 生成可执行性、检测准确性、新增覆盖/迁移、RAG/反馈贡献、缓存/发布再用 | 项目测试、专项测试集测试、工程流程用例测试 |

同一材料可服务多个功能；每次实验明确主要功能、意图、类型、任务与计分单位。项目改进版本和执行批次另行关联。原通用基准/专项同任务划分保留在历史协议中，作为对照策略，当前目录按三个功能组织。

## 当前入口

- [仓库论文全文与阅读包](../papers/README.md)、[可恢复测试数据包](../datasets/README.md)、[作者说明](../dataset-notes/README.md)：2026-10-11 资料归档入口。
- [项目完整测试方案·静态页面](../../docs/testing/project-test-plan.html)：可离线查看、导航和打印的HTML页面，完整展示统一方案。
- [项目完整测试方案](../../docs/testing/simple-three-module-test-plan.md)：三个模块的统一全量方案；RealVuln 26项目、OWASP 1230例、PatchEval 1000任务/230动态任务、QLCoder完整176项Java CVE配对任务，分别定义对照、指标和完成条件。
- [项目测试历史结果附录](../../docs/testing/project-test-status-appendix.md)：已收集成绩及其局限，与完整测试目标分开维护。
- [已收集测试项目：三级功能分类 v2](classification-draft-v2.md)：当前分类，32项材料逐项关联功能/意图/类型，内部工程测试落位到三个功能。
- [已收集测试结果分类表](collected-results-classification.md)：28条用途分类，关联23份结果/诊断报告及其改进版本；[配套索引](collected-results-classification.json)保留结果ID、哈希和版本收据。
- [历史草案 v1](classification-draft-v1.md)：保留本地材料盘点与六个JS项目的具体准入边界。
- [测试结果、环境与版本归档](../../docs/testing/README.md)：结果 ID、历史版本绑定、环境快照和不可覆盖的本地收据副本。
- [论文时效与对照覆盖核查](freshness-and-coverage-review.md)：首发/发表区分、实际比较缺口与补充优先级。
- [原通用基准计划](common-benchmarks/plan.md)：共同输入和公平对照的历史协议。
- [原专项同任务计划](specialized-comparisons/plan.md)：竞品任务匹配和复现条件的历史协议。
- [ABSENTIA专项方案](specialized-comparisons/absentia.md)：真实访问控制缺陷、修复前后配对与盲审。
- [当前测试对象统计](inventory.md)：32项材料、10个主要外部对照、8个方法候选。
- [当前文献逐项清单](../catalog/current-papers.md)：43项去重文献登记及本地全文状态。
- [机器清单](../manifests/current-test-inventory.json)：来源、语言限制、落地状态和PDF指纹。
- [实验状态](../experiments/state.json)与[工作日志](../experiments/journal.md)：恢复执行用；历史结果保持原样。

## 已有结果与下一步

2026-10-09 [新增补测](../../docs/research/supplemental-20261009-results.md)：96 个新 OWASP 文件、10 个修复联合判定任务、旧 Rule8 的新数据流正反例，以及可靠性/浏览器补测。精确范围、失败和未完成门槛详见报告；这些结果作为 VALIDATION-10-SUPPLEMENT 单列，旧成绩和旧归档保持。

通用测试已有一次冻结的OWASP48验收，实跑对照为CodeQL、Bandit和阿里Open Code Review；[结果及限制](../experiments/owasp48-final-comparison.md)。这48例评分后已经暴露，今后作为回归材料，新的验收需要换预留样本。

专项优先准备BAC-Bench：先冻结公开索引和目标源码，隔离答案，再校准匹配裁决。ABSENTIA目前公开数据，检测器代码尚未发布，因此现阶段可做同任务测试和作者结果参照；实际同配置竞品复现仍待代码发布。

10-08 的分类、统计和协议整理未追加付费模型测试；10-09 补测新增真实模型调用，调用收据与新报告分别归档。原始材料继续保存在原目录，防止破坏已有路径与固定指纹。

## 复核统计

在仓库根目录执行：

```sh
python3 scripts/benchmarks/current_test_inventory.py
```

脚本合并三个方向来源目录、既有书目、方法登记与最近竞品记录，核对本地文件并生成来源清单和文献表。其A/B字段保留原历史统计口径，当前三级功能分类查v2。32项是材料/任务候选条目，43项是文献登记，均不表示已全部下载、通读或复现。PDF按本地文件头与指纹核对，阅读范围仍查原研究记录。

2026-10-09 [真实 Worker／浏览器补测及各测试用途](../../docs/research/chain-completion-20261009-results.md)：230 项全量回归通过，新增 3 项归档保障通过；两语言实际上传／发现／复核完成，后续因测试定位问题及自动审批服务额度阻塞未完成。VALIDATION-10-CHAIN-COMPLETION 单列，禁止称全部链路通过。
