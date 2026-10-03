# 最早研究讨论回顾与本次调整

2026-10-03，已实际分页回读聊天“新增 AI 代码审计项目文档”，同时核对本地旧项目审查和 OpenCodeReview 运行记录。

## 需求沿革

1. 首先计划做“AI+传统静态代码审计”项目，研究阿里 OpenCodeReview；该工具当时已本地构建，但只运行 preview/delegate，未配置模型。此次将它作为主要 LLM 审查对照，不能写成已完成自身模型能力测评。
2. 论文最初希望以2026材料为主，之后明确2025代表作也可。故主文献优先2026，新版/正式版与首次公开年份分开；标准基准中旧CVE无需假装是2026漏洞。
3. 早期重点包含 SemTaint、SastBench、Friends or Foes、ARQ、QLCoder、IRIS，以及 RealVuln、腾讯VulnGym、CrossCommitVuln-Bench。新方案已补回这些，按当前Python/JS适配性筛选，而非只引用最新标题。
4. 旧平台问题是检索结果对不同安全需求几乎相同、候选无可靠锚点/去重、编译后即发布、生成规则污染默认扫描、失败被当零结果、报告条目重复计数。
5. 重写选择成熟框架与职责拆分；确定CodeQL、证据AI复审、隔离修复diff/报告、RAG规则四阶段。此次实现保留固定基线、真实证据和人工门槛，同时揭示尚不能证明的质量边界。

## 回顾后需要校正的论述

- “纯LLM”：OpenCodeReview主要判断依赖LLM，但还有确定性流程和工具；不能说完全没有非模型逻辑。
- “RAG生成QL创新”：QLCoder等已覆盖；需要版本/项目知识约束和独立留出验收的比较。
- “精准语义审计”：改为证据预算、弃权、主动取证机制；精准度由TP保留/FP降低/新增根因真值评估。
- “增量漏洞”：当前是固定快照中相对冻结基线的补充发现，不是Git跨提交增量。不同位置也不等于不同根因。
- “修复正确”：不能只看语法或告警减少；此轮int替换eval反例已说明功能可能受损。
- “基准真值”：SastBench近似FP、AACR评论标签、真实项目未标注告警的语义不同；不能混成同一种精确率/召回。
- “Java/C论文结果”：可引用方法，但尚未适配的语言不能计入本平台性能。

## 交付位置

本轮论文/材料/对照组/消融/真实模型待测项分别见 papers-and-innovations.md、competitors-and-materials.md、experiment-plan.md、benchmark-results.md。旧项目详细审查保存在父目录 outputs/platform-design-review/design-review.md；旧阿里演示在 outputs/open-code-review-demo.md。本轮不修改旧项目。
