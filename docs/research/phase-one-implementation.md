# 第一阶段实施记录

日期：2026-10-03。对应 [改进计划](phase-one-improvement-plan.md)。本文件区分已实现功能、实际验证与条件增强，不把待确认草稿当已通过规则。

## 功能与原因

| 项目 | 已实现的修改 | 原因与目标 | 验证/限制 |
|---|---|---|---|
| M1 调用治理 | stage保存非密钥配置快照、逐次模型调用、响应模型/finish_reason/推理token/耗时；共享调用数、token和时间预算；截断重生与结构纠错最多一次 | 定位并控制原有输出截断，避免无限重试及失败伪装安全 | HTTP契约测试含缺usage、截断、结构错误；未知usage使用保守预留预算而不填0；真实预算对照记录独立保存 |
| M1 可选思考模式 | 仅显式配置才发送thinking字段，默认None；SDK隐式重试继续关闭 | 验证是否能减少推理预算耗尽，同时不将不支持参数发给其他provider | 当前用户端点简短请求HTTP200、reasoning_tokens=0；关闭思考的规则对照仍出现编译错误，未修改默认模式 |
| M2 复审v2 | anchor_assessments / candidate_assessments / new_findings分开；严格位置模型、真实引用、ID归属、范围与重复检查 | 良性锚点评价不再制造待确认漏洞；不同CWE结论可以并存 | 锚点/候选结论需该位置源码；完整结果与阶段完成状态同一事务，错误或取消不得部分保存 |
| M2 历史与展示 | 新API阶段prompt v2；旧stage/v1 prompt仍可读取与恢复；CWE/model_assessment与人的status分开 | 保留旧输入与历史，不用模型推荐冒充确认 | 历史新字段unknown；不根据旧标题猜CWE；前端展示锚点评价、未评估范围、调用记录和候选模型建议 |
| M3 知识 | 固定版本CodeQL查询参考20条及项目指南2条；来源/许可/依赖/API版本/hash清单；按章节保留完整代码块；导入去重、检索内容去重、语言/owner/API版本过滤 | 提高知识可追溯性，避免API版本错配；补强真实RAG而不是伪造向量知识 | 这些参考多为查询入口，并不等于完整API知识；类型错误已暴露库声明资料不足。用户导入不能冒充官方可信来源 |
| M3 用途与验收 | purpose与strategy分别记录；12个server-owned独立微样本集，覆盖Python/JS、eval/SQL/XSS、锚点/漏洞规则；生成样本与独立样本分栏 | 编译成功不能替代漏洞准确率；良性、常量、别名/同名函数根据规则用途分别标注 | 现代规则未独立验收不能发布；framework_model强制提供模块，但尚无对应完整框架集，不能发布未经集成验收的模型规则 |
| M3 完整性 | 验证指纹覆盖query/modules/dependencies/purpose/generated fixtures/holdout_id；发布与执行时检查独立集hash | 防止改依赖/样本/用途后沿用旧验证 | 历史purpose=unknown的v1已发布版本保留旧校验语义，并标legacy未独立评估；不声称其满足新门槛 |

## 配置与升级

1. 后端执行 `alembic upgrade head`，迁移 `965a0de5fd52`；新列通过unknown/空容器填充，原审计历史不改写。已在本地执行，`alembic check`通过。
2. 新环境使用 `scripts/curate_codeql_knowledge.py` 导入已安装固定版本查询资料。来源许可见 `codeql-knowledge-license.txt`，内容hash与版本见 `codeql-knowledge-manifest.json`。脚本只读取本地包，不自动下载第三方仓库。
3. `AI_REVIEW_TOKENS / AI_REPAIR_TOKENS / AI_RULE_TOKENS` 为0时沿用全局6000；阶段默认最多24次调用、100000 token、300秒。恢复计入同一总预算；预算不足返回未知，不静默缩小审计范围。
4. `AI_THINKING_MODE`默认未设置；只有确认provider支持后才显式选择enabled/disabled。实验组通过stage快照单独设置，不写入默认 `.env`。
5. embedding未配置，实际生产检索仍为BM25；vector/hybrid检索要求真实索引，否则明确报错。尚未完成真实向量/融合质量消融，不计为性能提升。
6. 新规则可先生成草稿；发布前需选择匹配语言、用途的独立集并完成样本评审和实际验收。用户未选择或独立集失败时规则为draft，保留日志供修订。

## 回滚边界

保留本次前的commit及数据库备份；回滚应用前停止新任务。数据库downgrade会删除新增调用/用途等字段，不能当作无损操作，本轮未执行。历史prompt与不可变产物不替换；重跑创建新stage。模型密钥未写入任何迁移、脚本、报告或Git。

## 测试

普通代码/API回归67 passed、1 deselected；真实工具集成单独1 passed。TypeScript/Vite构建及真实模型结果见[测试汇总](phase-one-test-results.md)。首次CLI集成发现验证结果访问已关闭Session的问题，已修复并新增回归；重跑完整链路通过。此集成使用显式ScriptedModel验证协议，不能作为真实模型质量成绩。

真实模型组使用现有隔离研究owner与不可变微样本；预算组、规则需求组、thinking控制组各自保留失败、引用知识版本与实际响应用量。研究评审批准仅限逐条读过的锚点源码/样本，不自动批准未来草稿、不发布规则、不覆盖原代码。

GUI未测试，界面只经过静态检查和构建；手动校准条目见 `docs/acceptance-checklist.md`。

补充库API语料通过 `scripts/curate_codeql_library.py` 导入隔离实验owner，清单见 `codeql-library-manifest.json`；三轮关闭思考的库知识实验仍为编译/契约失败，未提升生产默认效果。2026-10-03复查显示该组候选/详细诊断留存不足，具体失败步骤不可还原；详见[论文与新方案](rule-generation-redesign-plan.md)。
