# 两类测试的统一入口

更新：2026-10-08。按用户要求，将测试组织为两类；漏洞发现、规则生成、代码修复是每类测试的能力标签。

| 类别 | 回答的问题 | 输入与计分 | 主要对照 |
| --- | --- | --- | --- |
| A：通用基准测试 | 在共同数据集上，平台相较常规工具表现如何？ | 同样的源码、样例、CWE口径和环境；准确率、召回、误报、耗时和成本 | CodeQL、Bandit、Semgrep CE、阿里 Open Code Review，以及平台消融 |
| B：专项同任务测试 | 在某个竞品或论文的目标任务上，平台表现如何？ | 对齐其原始项目、版本、任务定义、输入权限及评分；另列模型/预算差异 | ABSENTIA/BAC-Bench、IRIS、RepoAudit、QLCoder/CQLLM、修复与复审方法 |

同一材料可服务不同任务，但每次实验必须声明一个类别、一个任务和一个计分单位。不能把告警复审、漏洞发现、QL编译和修复成功率混在同一排行榜。

## 当前入口

- [论文时效与对照覆盖核查](freshness-and-coverage-review.md)：首发/发表区分、实际比较缺口与补充优先级。
- [A类计划](common-benchmarks/plan.md)：通用基准及三条能力的门槛。
- [B类计划](specialized-comparisons/plan.md)：竞品任务匹配和复现条件。
- [ABSENTIA专项方案](specialized-comparisons/absentia.md)：真实访问控制缺陷、修复前后配对与盲审。
- [当前测试对象统计](inventory.md)：32项材料、10个主要外部对照、8个方法候选。
- [当前文献逐项清单](../catalog/current-papers.md)：43项去重文献登记及本地全文状态。
- [机器清单](../manifests/current-test-inventory.json)：来源、语言限制、落地状态和PDF指纹。
- [实验状态](../experiments/state.json)与[工作日志](../experiments/journal.md)：恢复执行用；历史结果保持原样。

## 已有结果与下一步

通用测试已有一次冻结的OWASP48验收，实跑对照为CodeQL、Bandit和阿里Open Code Review；[结果及限制](../experiments/owasp48-final-comparison.md)。这48例评分后已经暴露，今后作为回归材料，新的验收需要换预留样本。

专项优先准备BAC-Bench：先冻结公开索引和目标源码，隔离答案，再校准匹配裁决。ABSENTIA目前公开数据，检测器代码尚未发布，因此现阶段可做同任务测试和作者结果参照；实际同配置竞品复现仍待代码发布。

本次完成分类、统计和协议整理，没有追加付费模型测试。原始材料继续保存在原目录，防止破坏已有路径与固定指纹。

## 复核统计

在仓库根目录执行：

```sh
python3 scripts/benchmarks/current_test_inventory.py
```

脚本合并三个方向目录、既有书目、方法登记与最近竞品记录，核对本地文件并生成机器清单和文献表。32项是材料/任务候选条目，43项是文献登记，均不表示已全部下载、通读或复现。PDF按本地文件头与指纹核对，阅读范围仍查原研究记录。
