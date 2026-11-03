# 正式实验的续接入口

更新：2026-10-08。本目录保存实验执行状态；测试项目分类与任务边界统一见[两类测试入口](../test-programs/README.md)。历史结果保持原样。

2026-11-02 用户新授权的代码审计机制研究独立入口：[实验协议](audit-mechanisms-protocol-20261102.md)、[诊断报告](../reports/audit-mechanisms-diagnosis-20261102.md)、[本研究状态](audit-mechanisms-state-20261102.json)。该研究按互补发现、前提复审、反馈补证展开；下文与 `state.json` 保留此前总体/修复任务的历史状态。

## 每次继续工作先读什么

1. [状态文件](state.json)：任务状态、依赖、当前阶段和下一步。**执行状态以此文件为准。**
2. [两类测试计划](../test-programs/README.md)：通用基准与专项同任务；[原总计划](plan.md)保留研究问题及正式门槛。
3. [首批项目与选样规则](first-batch.md)：本轮具体材料、用途、排除规则。
4. [执行与断点恢复规程](runbook.md)：输入隔离、产物契约、预算和中断处理。
5. [工作日志](journal.md)：只读最近一条及其引用；需要追查决策时再读历史。

需要评分细则时再读 [评测协议](../evaluation-protocol.md)，需要来源时查 [材料目录](../README.md)。不必重新阅读全部聊天记录。

## 现在的位置

三个方向的首轮检索/接入校准、发现链路整改及OWASP48循环/冻结验收已完成。最新实跑对照是CodeQL、Bandit和阿里Open Code Review；[冻结结果](owasp48-final-comparison.md)保留同批评分与成本。RAG规则与修复已有开发测试，正式隐藏任务仍未完成准入。

最新整理：[当前材料和竞品统计](../test-programs/inventory.md)、[文献登记](../catalog/current-papers.md)、[ABSENTIA专项](../test-programs/specialized-comparisons/absentia.md)。本次分类整理未追加付费调用。

以下是历史校准/整改的追溯入口：

- [首轮实测结果](calibration-results.md)：有效结果、失败、测试配置修正与结论范围。
- [收据生成的统计](calibration-summary.json)：本次99次文本调用，未宣称论文提升。
- [论文原表对齐](paper-baseline-alignment.md)：作者成绩及同榜比较条件。
- [下一轮改进与验收](calibration-followup-plan.md)：输入/oracle、复审窗口、语义上下文和目标规则校验。
- [追加失败溯源](failure-analysis.md)：具体工具异常、SQL/NoSQL错配、诊断误判及已有候选补丁的事后检查。
- [漏洞发现整改与复测](discovery-retest-results.md)：指定三项已修复，同池59候选全部复审，新增4个源码支持主根因；完整发现覆盖仍待扩大。
- [输入与检查覆盖整改结果](discovery-coverage-results.md)：81/81本轮业务窗口、124/124候选有结论；严格主条件暂定支持24/31，输入与完整覆盖预算扩大，不能归因于同预算提示增益。
- [下一阶段语义判断与流程可靠性方案](../../design/discovery-semantic-improvement-plan.md)：同池复审没有根因净增，先处理候选失败隔离、实际操作定位、必要前提取证与矛盾结论。

下一项是 **两类任务的输入准备与门槛补齐**：通用发现采用新预留样本；专项先冻结BAC-Bench索引、上游源码与根因裁决。ABSENTIA检测器未发布，不标成已实跑竞品。规则/修复的暴露审计、参考QL可解性和联合oracle仍待补齐；具体执行从状态文件`next_action`开始。

## 决策优先级

- 用户最新要求优先；本计划覆盖旧文档中实验组织、默认对照和范围的冲突。
- 三条主线：双引擎发现、RAG 规则生成、语义辅助修复；速度和成本在三条主线上统一测量。
- Python / JavaScript 为主，TypeScript 单列支持率；Java / C / C++ 暂作论文方法参考。
- CodeQL 主对照沿用相同的生产查询套件，不在本轮增加扩展套件；实际名称和 pack 版本必须在 E00 核实。
- 修复产品链路暂不加入利用复测；实验先筛选纯单元可验证任务，不启动目标服务，不做 GUI 测试。
- 本轮测试材料不写入生产 RAG。开发样例、隐藏答案、模型运行产物分开保存。

状态和日志必须在切换模型、结束工作或上下文压缩前更新。下一位执行者从 `next_action` 开始，先检查已有产物，不能将“已下载”直接当成“测试通过”。
