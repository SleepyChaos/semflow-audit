# RAG 材料扩充与开发验证结果

日期：2026-10-04。旧 v3 结果保留在 [历史报告](rag-corpus-expansion-v3-results.md)；本报告更新到 v4，不覆盖旧实验或失败日志。

## 规模与质量

| 指标 | 初始批次 | v3 扩库 | v4 开发验证后 |
|---|---:|---:|---:|
| 独立参考原文来源 | 40 | 271 | **271** |
| 完整官方规则范例 | 28 | 141 | **141** |
| 官方开发测试通过、可用范例 | 22 | 22 | **130** |
| 仅编译检查通过、可用范例 | 0 | 113 | **8** |
| 开发测试失败、排除范例 | 6 | 6 | **3** |

271 是不同 API/框架原文来源，不能称 271 种漏洞或独立业务主题。141 是正式清单中的完整查询，按语言/查询来源去重；历史导入别名、切片、测试组不增加范例数量。130＋8＝138 个合格范例与全部 271 条参考原文已有当前配置身份的真实 embedding 索引。

| 语言 | 参考原文来源 | 完整范例 |
|---|---:|---:|
| Python | 103 | 44 |
| JavaScript | 168 | 97 |

知识包含安全数据流、框架模型、API 图、Source/Sink/Sanitizer/传播摘要、Web/数据库/模板/网络/序列化等。仍需后续补充漏洞原理教程、框架行为说明、真实编译修正案例和跨框架安全反例；更多 `.qll` 不等于完整知识体系。

## 官方开发测试与真实来源

- 固定 CLI 2.23.5，Python 库 4.0.10 / queries 1.6.0，JavaScript 库 2.4.0。
- 官方测试组共执行 **136** 个，**133 通过、3 失败**。其中 3 个通过组所属的查询超出完整范例大小门槛，未纳入可用范例，因此 133 个通过测试组不等于 133 条可用查询；正式清单只有 130 个开发测试通过范例。
- 收集对应官方测试的源文件、预期、查询、私有/传递辅助模块、父级 options、依赖锁。补齐此前遗漏的 7 个 JSX/Vue/XSJS/RAML 文件。所有原文和测试输入绑定固定 Git blob 与哈希，日志和 receipt 保留；没有改写查询逻辑或测试金标。
- 仍失败：JavaScript UnsafeHtmlConstruction、ClientSideUrlRedirect；Python StackTraceExposure。当前失败版本从生成范例检索排除，旧通过版本不会被重新激活。
- JavaScript SQL 采用同一固定官方 commit 的 **untyped 官方测试组**，保持其原始金标并通过。此前 typed 组仍未定位解决，不能声称 typed 测试已修复。真实 SQL 查询同时标记 CWE-089/090/943，已按实际标签建立多 CWE 过滤。
- 当前有效来源选择按 owner/source 最新版本，再检查明确质量层级。编译通过与开发通过分开显示；未验证用户/历史范例不会被默认升级为合格 detector 范例。

固定来源：[Python build commit](https://github.com/github/codeql/tree/4ece8abc3032a266eb4b9839442d8be5084552ea/python/ql)、[JavaScript build commit](https://github.com/github/codeql/tree/c524a98eb91c769cb2994b8373181c2ebd27c20f/javascript/ql)。使用公开 MIT 原文，不把用户上传项目写入共享知识库。

## 索引与检索检查

真实模型 `doubao-embedding-vision`，返回 revision `doubao-embedding-vision-251215`、2048 维；与原文、模型 revision、维度、索引身份绑定。没有重排模型。历史向量/记录保持可追溯，不与当前有效数量混算。

两语言 × 10 CWE × BM25/hybrid，共 **40 项材料可用性检查，40/40 通过**，各模式 20/20。v3 为 36/40；SQL/NoSQL 缺口已补齐。检查使用 v4 文档范围、当前有效质量过滤，完整范例不截断。非空、版本和标签匹配仅说明材料可用，不能称检索准确率或证明向量优于 BM25。

## 数据库存储口径

此轮完成时，共 814 个文档版本、1110 个切片；公共 798 版本/1046 切片，私有文档版本仍 16 个。公共 reference 324 版本对应 271 来源；rule_example 470 版本对应 169 来源标识，含旧导入别名。974 个公共切片有当前向量身份，其中包含历史版本。**有效材料规模按正式清单 271＋138 判断，不按数据库行数判断。**

## 可复核产物

- 原文、开发测试、完整依赖、输入/执行/索引 receipt：`artifacts/materials/rag-corpus-v4/manifest.json`、`development-manifest.json`、`validated.json`。
- 40 项检索记录：`artifacts/research/corpus-coverage-v4.json`。
- 数据库历史计数：`artifacts/research/rag-inventory-v7-final-20261004.json`。其中 legacy inventory filter 的统计不等于新版生成器的有效范例筛选。
- 本阶段端到端效果和消融由单独冻结实验报告；扩库数量与官方开发测试不替代隐藏集检测效果。

后续 30 个版本化指南、20 个真实编译修正案例属于下一阶段质量扩充，当前不记为完成。未做 GUI 测试或漏洞利用复测。
