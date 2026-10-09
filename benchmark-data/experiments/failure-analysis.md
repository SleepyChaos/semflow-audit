# 首轮失败溯源与改进优先级

日期：2026-10-05；基于 `20261005-calibration-v1` 原始产物和产品源码。没有新增模型调用；追加执行了一个已有候选补丁的同边界 Docker 单元检查。原始正式/校准计数保持不变。

## 1. 原结果与比较边界

- 同输入 OWASP：CodeQL P/R/F1 为 47.92%/30.53%/37.30%；Bandit 为 81.20%/23.89%/36.92%。自定义精确 CWE adapter、1,230 案例；不是官方 scorecard。CodeQL 召回较高、Bandit precision 较高，尚无整套 AI 流程在 OWASP 上的成绩。
- 开发根因线索池：12/31→16/31；最终新增 supported 为0。语义修复原流程：旧3/3、新1/3有界联合通过。QL：18次中的5次持久化，隐藏正例均未命中。
- 作者原表是外部参照，没有可计算同榜差值的项；版本、语言、输入权限、反馈与样本分母差异见 [论文对齐](paper-baseline-alignment.md)。旧18项合成QL与本轮两个派生任务不相减。

## 2. 双引擎：工具参数恢复和覆盖调度

**已确认事实：** DVNA 四个复审批次全部 `incomplete`，reason均为“源码取证窗口无效或超过151行”。`EvidenceService.read` 拒绝 `end_line-start_line>150`；复审 prompt 列出工具但没有说明窗口上限。`UnifiedReview.verify` 将工具异常写成整批 incomplete，没有在该批返回合法窗口供模型纠正。

此外本次最多4批、每批4候选，43条候选最多覆盖16条；即便窗口不出错也不能覆盖全部。重复静态告警和粗筛假设消耗候选槽，源码条件、部署可利用性与缺业务合同需要不同确认边界。

**改进：** 在工具契约明确窗口、分页续读与EOF；非法参数转成可恢复观察，不取消整批；稳定根因分组共享证据、保留原记录；预算分配前计算覆盖能力，输出未审原因。Scout危险调用先验 import/符号绑定，避免把未定义 `rp()` 当popen。

**验收：** 同项目同总预算下，候选审查覆盖明显提高、确认新增根因且由独立evaluator核对；FP trap不确认为漏洞；unknown不当排除。若全量预算不够，优先队列和coverage必须显式报告。

证据：[DVNA复审收据](../../artifacts/research/formal/20261005-calibration-v1/discovery/rv-dvna/D3.json)、[读取校验](../../backend/app/services/evidence.py)、[批次异常处理](../../backend/app/services/unified_review.py)、[复审提示](../../backend/app/prompts/review.v4.txt)。

## 3. 修复：上下文膨胀之外还有错误诊断

### 第一次失败：第一次生成前已经超预算

从保存的 repair-context 按生产 `context()` 逻辑重建，首次 propose payload **45,819字符**，上限40,000字符；allowed_files 16,098、inspection 28,746。目标文件不是唯一大项：外部调用证据、语义摘要及inventory一起进入最终请求。代码已经压缩了目标文件的部分重复证据，仍没有按整体上下文预算选择必要外部片段。

### 第二次失败：已有有效候选，但诊断误判导致重试溢出

初始 propose 为 **38,057字符**，生成并应用了补丁。真实diff增加对双引号、单引号、换行、回车、制表符的过滤；old_text与new_text不相等。

产品只运行语法检查，返回 `needs_review`；`SemanticRepair.validate` 未将它作为passed，因此进入diagnose。诊断LLM却声称“old_text和new_text相同、补丁是no-op”，与真实diff矛盾，并归类implementation。下一轮加入上一候选、完整诊断和checks后，payload **44,046字符**，生成前被预算拒绝。

**追加事后检查：** 将这一已经存在的补丁交给同一有界模块oracle，功能+安全联合通过。收据：[posthoc oracle](../../artifacts/research/formal/20261005-calibration-v1/posthoc/repair-v2-round-2-existing-patch/oracle-result.json)。这说明第二次流程失败不能等同于“生成的代码修复无效”。原批次新方案1/3的完成计数不改写；事后检查单列，不能挑选结果替换原对照。

**改进：**

1. 证据持久化完整、上下文按当前待决问题选片段；项目摘要、业务不变量、目标代码、外部调用关系分层，引用稳定ID，去重复窗口。
2. 每轮按组件预估最终请求预算，加入反馈前做容量规划；用短错误差量替代重复candidate/完整diagnosis，保留原产物可读取。
3. 将静态语法通过但行为未评估保留为needs_review/unknown；只有真实失败断言才触发实现修复循环。无验证不应自动重写代码。
4. 诊断必须附真实diff和机器算出的changed/no-op事实，校验LLM关键断言；错误诊断不接受为下一轮修改依据。

**验收：** 当前单例三轮流程均形成可评测产物，不因无行为证据误触发循环；已有双oracle不退化；再扩大多个独立模块。不能只提高40K上限或模型预算掩盖冗余。

证据：[原round2](../../artifacts/research/formal/20261005-calibration-v1/repair/v2-round-2/generation.json)、[修复编排](../../backend/app/workflows/repair.py)、[上下文/诊断](../../backend/app/services/repair_semantics.py)、[字符预算](../../backend/app/services/context_materials.py)。

## 4. 规则：检索错配、模板复用、验收漏洞和测试入口四项叠加

### 检索有明确资料错配

五个持久化SQL草稿中，三次的Query/Customizations资料选中 **NoSqlInjection**，另外两次是正确SqlInjection资料。源码过滤使用 `title.contains('SqlInjectionQuery')`，NoSqlInjectionQuery也满足这个子串条件；Customizations同理。

这是可复现的检索角色筛选问题；数据库返回成功不说明资料适配正确。BM25与向量在此先受过滤影响，不能用最终QL成绩判断哪种算法更好。资料应使用结构化漏洞族/API模块/版本身份，避免模糊子串。

### 正确资料也没有带来目标建模

五个草稿query_hash相同，均直接导入标准 `SqlInjectionQuery` / `SqlInjectionFlow`。它们没有新增目标helper/框架的source、sink或传播模型，实际单规则原项目也零命中。两次正确资料仍无隐藏TP，因此“修检索就必然改善规则”尚未证明。

### 开发验收未要求实际目标命中

未传Candidate时 `project_replay.status=not_evaluated`；发布检查接受target_detected或not_evaluated。当前只凭source_paths的通用入口不能确认目标根因。持久化draft不代表已发布，但门槛允许未评估路径，不能据此称检测器可用。

### 测试任务自身可解性仍待校准

有界任务只保留testcase+helpers，没有完整app注册入口；生产静态基线也零命中。缺经验证参考QL，无法断言五次失败全部来自模型。匿名loader问题已在完整OWASP修正并重跑，但这不自动解决有界任务的入口模型。

**改进顺序：**

1. 完整输入/入口和参考QL先验证可解；开发正例、隐藏正例、安全变体均有独立预期。
2. 用结构化资料/API匹配修正SQL/NoSQL串匹配，人工相关性qrels独立评价检索。
3. 生成明确source→传播/helper→sink→guard模型，绑定实际API证据；复用官方模板时说明哪些模型已有、哪些需要新增。
4. 从源码描述构造明确目标条件；单规则必须命中实际目标，开发自造样例不替代它。未评估/零命中保留失败草稿，不能标有效检测器。
5. 分开“目标命中”和“基线新增”；用独立隐藏负例和跨仓库条件验迁移。再支持真正NoRAG及纯检索对照。

**验收：** 先通过参考查询校准，再在同预算下提高原项目目标命中及隐藏正负例联合通过；目标本已被CodeQL覆盖则不能称新增漏洞检测。

证据：[retrieval标题过滤](../../backend/app/adapters/retrieval/knowledge.py)、[双库角色](../../backend/app/adapters/retrieval/dual_corpus.py)、[目标验证](../../backend/app/services/rule_project_validation.py)、[原生成统计](calibration-summary.json)。

## 5. 下一步排序

**P0实验可解性与输入身份 → P1工具恢复/复审覆盖 → P2修复上下文与诊断事实校验 → P3规则结构化检索及目标模型 → 同任务新run回归 → 正式同子集论文对照。**

速度优先减少重复取证、无效诊断和重试，质量通过后再测独占机器的真实并行墙钟。当前证据不支持优先换模型、无限提高预算或只扩大知识库；这些因素可后续消融，不是这批失败已经确认的单一根因。
