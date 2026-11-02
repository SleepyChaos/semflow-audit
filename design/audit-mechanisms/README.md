# 代码审计模块的三个机制

更新：2026-11-02。本组文档回答三个问题：候选为什么能补充发现、复审为什么可能提升精确率又损失召回、补证如何改变可判断的信息条件。

1. [静态分析与语义审计的互补发现](complementary-discovery.md)：双分支、任务覆盖、规则/语义/输入/评分四轴归因，以及309个Scout独有命中的解释边界。
2. [基于成立条件的证据复审](premise-review.md)：三前提账本、可控输入/危险操作/有效防护/授权要求，引用与推理的区别，以及precision收益中的CWE计分因素。
3. [发现与复审之间的反馈补证](evidence-feedback.md)：DVGA原始失效路径、本地修复的状态流、证据缓存与新读取、预算和失败语义，以及当前回归能证明什么。

三份文档都将事实、机制解释和待检验假设分开。本文可核验的最新完整RealVuln归档为**2026-10-14冻结六组实验**；2026-11-02为归档核对、机制诊断及本地修复回归日期，不包含同学正在服务器开展的新增测试。新回归使用显式模型替身，不冒充RealVuln新成绩，也不代表服务器版本已更新。

关联材料：[机制实验协议](../../benchmarks/experiments/audit-mechanisms-protocol-20261102.md)、[历史诊断](../../benchmarks/reports/audit-mechanisms-diagnosis-20261102.md)、[六组完整报告](../../benchmarks/reports/realvuln-ablation-20261014-results.md)。
