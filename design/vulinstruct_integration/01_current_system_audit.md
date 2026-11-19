# 现有系统审计与基线

冻结提交为 `d248a869fb5966033cb2e0599dfb527f7ad3954e`，分支为 `codex/review-remediation`。开始时工作树干净。Python 为 3.14.8，工作区锁文件 SHA-256 为 `5404179efb760cc731da8ebc3e3dfbfc2841c3927ab218a972bd47375f6bb2c5`。按 `AGENTS.md`、`design/architecture.md`、`system/collaborator-setup.md` 和 D 盘实验工作区的《实验协议》核对入口。

## 发现阶段

- `system/research/src/semflow_research/runtime/discovery_operations.py:28` 验证冻结查询包与套件，再通过 `adapters/codeql/scanner.py:35` 建库、`:73` 扫描，保留 SARIF 和已关联源码的候选。套件决定能运行哪些已有查询。没有用户 CWE 预选参数。
- `runtime/dual_discovery.py:132` 在任何分支启动前冻结两条请求。扫描和 Scout 各自有记录空间，统一复审才读取两边的候选。候选身份和根因关联分别保存，位置接近不能代替根因匹配。
- `discovery/scouting.py:62` 按源码清单建立项目地图。`discovery/scout_inspection.py:54` 按范围和第三方策略筛选代码窗口，`:79` 分配模型调用，`:119` 组装源码页、路由信息和符号绑定。Scout 支持多类安全属性，不要求输入 CWE。窗口、上下文、调用和目录范围会限制覆盖。未检查窗口必须与已检查但未发现区分。
- `public/corpus.py` 和 `runtime/corpus_inputs.py` 已支持语料冻结与摘要校验。`adapters/retrieval/knowledge.py:39` 提供 Haystack BM25、冻结向量余弦与融合；最多读取 1,000 条，规则生成已有场景级路由。新增增强可以复用检索器，并使用独立、明确选择的规范快照。当前 Scout 尚无规范检索入口。

## 复审阶段

- `discovery/review_pool.py:22` 统一装配候选，`:233` 装配当前批次源码。已有源码页、调用者、文本搜索、项目地图、Python 绑定、前端与配置导航。上下文装不下会留下状态，不能把未供给源码当作已读。
- `discovery/review_gap_planner.py:43` 和 `review_navigation_feedback.py` 提供有界缺口调度。策略 3 允许把运行时描述中的本地线索交给源码定位器。按需正文和缓存都使用原始快照与证据标识。
- `discovery/review_obligations.py:95` 生成分领域的成立义务。已有宿主核验集中在 Python 局部调用和少数直达路径。未独立证明的正向结论保留 `insufficient`。产品的排除态为 `excluded`，布尔式 TP/TN 需要评测端独立映射，历史引用或模型信心不能直接作为证明。
- 旧报告显示 DjanGoat 的前端与服务端路径仍需分开核查。Vulpy 历史回放保留本地控制与调用线索，Flask_XSS 先导记录中模板补页后曾获得支持。PyGoat 相反，实际局部实现只有空操作。二者不能用一个整体 F1 推导补证效果。真实独立复审配对曾被服务端 403 阻断，因此没有泛化结果。

## 新增边界

可选增强在同一 Scout 模式内接入。每个模式继续执行同样的自主安全检查，查不到规范按原路径完成。规范文本与源码证据分离，后续复审只将规范当作待查约束。语料授权、时点隔离、预算、失败状态和候选来源需要持久回执。修复与规则内核保留历史入口。

上轮定向套件 70 项通过。扩大范围 172 项通过、3 项跳过，16 项非本次范围失败在冻结基线复现。当前阶段以新鲜定向回归、冻结语料检索和可复核审计产物继续验证。
