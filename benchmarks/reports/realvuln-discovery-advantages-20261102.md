# RealVuln 漏洞发现优势项目与消融证据

整理日期：2026-11-02。原实验为 2026-10-14 六组消融；本次只对冻结产物做项目／金标级分析，未新增模型或扫描调用。

## 报告和证据入口

- [完整六组实验报告](realvuln-ablation-20261014-results.md)：主成绩、交集、复审去向、失败、成本和协议偏差。
- [最新测试现状核查](audit-testing-status-20261102.md)：与其他工具比较、历史版本、作者输出缺失及共同项目口径。
- [冻结实验协议](../experiments/realvuln-ablation-protocol-20261014.md)：26 项目／676 漏洞／120 陷阱，固定实现、输入和评分器。
- [原逐项目消融表](../../artifacts/research/realvuln/20261014-ablation/ablation-per-project.csv)：A～F 共 156 行。
- [本次项目优势表](../../artifacts/research/verification/20261102-realvuln/advantages/project-advantages.csv)：六组 TP、F 的 FP、增益与损失及外部工具结果。
- [逐项目外部比较](../../artifacts/research/verification/20261102-realvuln/advantages/external-project-comparison.csv)：156 行，包含作者保存运行次数与缺失状态。
- [252 个相对 CodeQL 新命中明细](../../artifacts/research/verification/20261102-realvuln/advantages/added-gold-cases.csv)：金标 ID、主 CWE、路径／行号、候选 ID、历史复审理由及作者保存运行是否全部漏掉。
- [本次分析脚本](../experiments/analyze_realvuln_advantages.py)：离线读包，校验 2,429 个 manifest 条目，不连接模型或服务。

这里的“新命中”指本系统 F 命中、CodeQL A 未命中的基准金标，不表示新发现了此前未知的真实世界漏洞。

## 优先分析哪些项目

先研究相对 CodeQL 增量较大、且对已保存 LLM 输出也有 TP 优势的项目；再加入失败对照。
下面列出优先案例，外部数值为保存输出的项目内 TP 均值取整，缺失不填零。
TP 更高不等于该项目的精确率、成本或总体质量更优。

| 项目 | CodeQL TP | 本系统 F TP／金标 | 净增 TP | F 的 FP | Sonnet TP | Gemini TP |
|---|---:|---:|---:|---:|---:|---:|
| pygoat | 16 | 46/70 | +30 | 78 | 32 | 28 |
| vulpy | 10 | 32/54 | +22 | 37 | 18 | 19 |
| djangoat | 12 | 27/50 | +15 | 50 | 17 | 15 |
| dsvpwa | 3 | 21/32 | +18 | 12 | 18 | 18 |
| flask-xss | 1 | 14/28 | +13 | 13 | 11 | 12 |
| dvblab | 8 | 16/22 | +8 | 16 | 15 | 13 |
| vulnpy | 6 | 30/78 | +24 | 17 | 53 | 67 |
| damn-vulnerable-graphql-application | 0 | 12/35 | +12 | 11 | 14 | 14 |
| vulnerable-api | 0 | 8/14 | +8 | 0 | 10 | 9 |

PyGoat、VulPy、Djangoat、DSVPWA、Flask-XSS、DVBLab 在双方已有输出的条件下，TP 都高于 Sonnet/Gemini 的保存均值。
其中 PyGoat 对 Sonnet 的 3 次保存运行，F 命中的 19 个金标在三次中均未命中；对 Gemini 的三次则为 16 个。
VulPy 对应为 15／12 个。这些是已保存运行上的集合差异，不表示模型原则上无法检出。
完整外部表保留了本系统漏掉的其他金标，不能只用此差集证明总体领先。

两个有价值的对照：

- VulnPy 对 CodeQL 增益 +24，但 F 的 TP30 明显低于 Sonnet53/Gemini67，适合检验“静态盲区补全”是否只是一般 LLM 能力，或受候选覆盖／预算限制。
- GraphQL 项目从 CodeQL0 提升至 F12，但 Sonnet/Gemini 均14。适合分析框架入口与分发建模，不足以单凭此证明优于其他 Agent。
- Vulnerable API 从 CodeQL0 到 F8、FP0，适合作为较小的入口建模案例；仍漏6条，Sonnet/Gemini为10/9。

按 TP 逐项目比较，F 对 CodeQL 为 26 胜／0 平／0 负；对有保存输出的 Sonnet 为 9 胜／0 平／14 负（23 项）；
对 Gemini 为 10 胜／3 平／11 负（24 项）。对 Kolega 为 0 胜／2 平／24 负。
这些胜负不替代总量微平均，也未控制模型／成本／运行次数差异。

## 六组消融能说明什么

A=CodeQL；B=独立 Scout；C=A＋B；D=A＋Review；E=B＋Review；F=C＋Review。

| 组 | TP | FP | 精确率 | 召回率 | F1 | F3 |
|---|---:|---:|---:|---:|---:|---:|
| A | 106 | 297 | 26.30% | 15.68% | 19.65 | 16.34 |
| B | 389 | 534 | 42.15% | 57.54% | 48.66 | 55.52 |
| C | 416 | 910 | 31.37% | 61.54% | 41.56 | 56.14 |
| D | 110 | 63 | 63.58% | 16.27% | 25.91 | 17.58 |
| E | 311 | 210 | 59.69% | 46.01% | 51.96 | 47.09 |
| F | 354 | 366 | 49.17% | 52.37% | 50.72 | 52.03 |

已得到的机制线索：

1. **发现增益主要来自独立 Scout。** F 相对 A 的252个新命中中，250个已被独立 B 命中。
   剩余两个是 PyGoat `pygoat-053` 和 Python App `realvuln-python-app-002`；前者已有官方顺序分配歧义记录，不能直接解释成 Review 创造了新发现。
2. **两路发现有互补，但不是无代价。** 独立 A/B 共同80、CodeQL独有26、Scout独有309、共同遗漏261。
   独立并集415与 C416 的一条差异来自评分分配顺序；不把集合数机械相加解释成新根因。
3. **Review 主要体现输出筛选／分类，而非净增召回。** C→F 的 TP416→354、FP910→366，P+17.79pp、R−9.17pp。
   旧命中保留353、丢失63、增加1。D/E/F虽统一Review实现，上游仍沿用冻结的增量Scout历史，不是全链统一重跑。
4. **归一化影响不能当成推理收益。** D 的 FP297→63，其中大量来自多CWE收敛、重复／重新匹配；并非234次独立的语义误报排除。

因此现有六组是模块级对照，足以定位 Scout 与 Review 的总体作用，尚未隔离“任务规划”“框架上下文”“主动取证”“证据契约”等内部机制。

## 252 个新增命中主要是什么

按基准 primary_cwe 统计，每个新增金标计一次。这里用金标描述来做事后归因，未把这些分类输入原模型。

| 主 CWE | 类型概括 | 相对 CodeQL 新增命中 |
|---|---|---:|
| CWE-79 | XSS | 50 |
| CWE-798 | 硬编码凭据 | 45 |
| CWE-89 | SQL 注入 | 17 |
| CWE-639 | 用户可控标识导致的授权问题 | 13 |
| CWE-78 | 命令注入 | 8 |
| CWE-502 | 不安全反序列化 | 8 |
| CWE-918 | SSRF | 8 |
| CWE-200 | 敏感信息暴露 | 7 |
| CWE-1336 | 模板注入 | 6 |
| CWE-352 | CSRF | 6 |

其余84条分布于另外41个主CWE。XSS50＋硬编码凭据45，共95/252（37.70%）。
这说明“默认规则／框架覆盖之外的源码发现”值得研究，但现在不能将全部252条都解释为复杂授权或业务逻辑推理。
同一 vulnerability_class 可以对应多个 primary_cwe，不能把两种分组混加。

## 从具体案例形成机制假设

以下依据冻结金标与当时的 Review 理由选取；本次没有重新获取完整源码做独立盲审。
历史模型理由只是分析线索，不直接当作通用机制已被证明。

| 案例 | 当时记录的源码条件 | 可验证的机制假设 |
|---|---|---|
| PyGoat `pygoat-003`，CWE-79 | view 接收 q，Django 模板 `query|safe` 关闭转义 | 跨 view／模板的框架语义上下文有助于补全静态默认套件遗漏 |
| VulnPy `vulnpy-001`，CWE-78 | 请求取值经动态触发器分发到 `os.system` | 导入／调用绑定和分发上下文有助于找到抽取模型之外的输入到危险操作路径 |
| DSVPWA `dsvpwa-001`，CWE-89 | 通用 handler 传递 handler.params，攻击类拼接到 SQL | 按操作组织证据页、定向补读上游模块可能比固定代码窗口更有效 |
| PyGoat `pygoat-014`，CWE-862 | 登录检查存在，实际角色权限检查缺失；相邻入口提供管理员要求线索 | 分别核查“保护义务”与“实际保护”，可避免将认证等同于授权 |
| GraphQL `dvga-013`，CWE-639 | mutation 直接按请求 id 更新 Paste，存在 owner 字段但未校验所有权 | 对象归属条件与 GraphQL 可达入口的联合取证可能补全授权发现 |

这些案例的匹配包含基准允许的CWE兼容与位置容差，部分历史理由与金标主CWE未完全同名。
正式论文案例需逐一检查原始源码、调用绑定、控制路径和判定依据，避免把匹配容差当成精确解释。

## 适合进一步验证的贡献方向

建议从“结果现象→实际机制→控制变量实验→新项目复现→文献查新”推进。
先从优势项目形成假设，再在新样本验证；当前表格不能单独证明学术新颖性。

| 候选贡献方向 | 已有证据 | 当前缺口 | 应补的同预算对照 |
|---|---|---|---|
| 基于源码操作与检查任务覆盖的独立发现 | B 的召回57.54%；250/252新增金标已在B命中；冻结Scout有inspection_tasks和route检查回执 | 尚未证明增益来自覆盖调度，而非更多模型调用或一般Agent能力 | 同模型／token／调用预算，固定窗口扫描 vs 操作任务规划；单列已覆盖任务与漏洞命中 |
| 框架与局部控制上下文驱动的主动取证 | view/模板、动态触发器、GraphQL/handler案例；冻结实现提供bindings、route和补读取证 | 现有六组未独立移除这些上下文；CodeQL漏检可能受默认套件或抽取覆盖影响 | 同一候选池，移除框架上下文／绑定／补读工具；同时检查CodeQL抽取与扩展套件 |
| 前提分解、证据校验与弃权的复审 | Review区分operation、input_or_policy、unsafe_protection；C→F提高P但损失R | 未与普通LLM复审隔离；收益掺杂CWE规范化；307个未决不能视为安全 | 同池同Prompt预算，普通复审 vs结构校验 vs源码证据门；统一输出归一化，报告风险-覆盖与原TP损失 |
| 静态与模型发现的可追溯合流 | 独立CodeQL仍有26条Scout未命中的金标；保留候选来源和证据ID | “CodeQL＋LLM”组合本身不足以构成新颖性；需证明合流策略超出简单并集 | 简单并集 vs按根因/证据关联合流；固定匹配、去重和分类口径，检查互补覆盖 |

不能由本轮发现实验推出 RAG 规则生成或修复贡献：它们有各自实验，且本轮所记录取证主要是源码读取与搜索。
也不能因为调用了 LangGraph、多阶段 Agent 或结构化输出，就直接把框架能力写成方法创新。

## 全部26项目六组TP，供选择与反例检查

按 F−A 的净TP增量排序；不要只选前几项报告总体效果。

| 项目 | 金标 | A | B | C | D | E | F | F−A |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pygoat | 70 | 16 | 47 | 49 | 16 | 34 | 46 | +30 |
| vulnpy | 78 | 6 | 33 | 33 | 6 | 33 | 30 | +24 |
| vulpy | 54 | 10 | 37 | 38 | 10 | 29 | 32 | +22 |
| dsvpwa | 32 | 3 | 23 | 23 | 3 | 20 | 21 | +18 |
| djangoat | 50 | 12 | 28 | 31 | 11 | 23 | 27 | +15 |
| flask-xss | 28 | 1 | 17 | 17 | 1 | 13 | 14 | +13 |
| damn-vulnerable-graphql-application | 35 | 0 | 18 | 18 | 0 | 9 | 12 | +12 |
| extremely-vulnerable-flask-app | 28 | 4 | 16 | 18 | 4 | 13 | 15 | +11 |
| lets-be-bad-guys | 24 | 4 | 14 | 15 | 4 | 12 | 14 | +10 |
| owasp-web-playground | 29 | 2 | 17 | 18 | 2 | 11 | 12 | +10 |
| dvblab | 22 | 8 | 15 | 16 | 8 | 15 | 16 | +8 |
| python-app | 20 | 5 | 13 | 14 | 6 | 11 | 13 | +8 |
| threatbyte | 24 | 3 | 16 | 17 | 3 | 10 | 11 | +8 |
| vulnerable-api | 14 | 0 | 9 | 9 | 0 | 8 | 8 | +8 |
| vulnerable-python-apps | 22 | 2 | 16 | 16 | 2 | 10 | 10 | +8 |
| dvpwa | 22 | 1 | 11 | 11 | 1 | 8 | 8 | +7 |
| vulnerable-flask-app | 20 | 3 | 9 | 10 | 4 | 8 | 9 | +6 |
| vampi | 13 | 1 | 9 | 10 | 1 | 6 | 6 | +5 |
| damn-vulnerable-flask-application | 15 | 3 | 8 | 8 | 4 | 7 | 7 | +4 |
| dsvw | 27 | 10 | 4 | 14 | 10 | 3 | 14 | +4 |
| vfapi | 9 | 1 | 5 | 5 | 1 | 5 | 5 | +4 |
| insecure-web | 9 | 4 | 7 | 8 | 4 | 7 | 7 | +3 |
| python-insecure-app | 8 | 0 | 3 | 3 | 1 | 2 | 3 | +3 |
| vulnerable-tornado-app | 14 | 4 | 7 | 7 | 4 | 7 | 7 | +3 |
| intentionally-vulnerable-python-application | 7 | 3 | 5 | 6 | 3 | 5 | 5 | +2 |
| pythonssti | 2 | 0 | 2 | 2 | 1 | 2 | 2 | +2 |

## 下一步建议

优先审阅 **PyGoat、VulPy、Djangoat、DSVPWA**，每个项目选2～3个机制不同的新增命中，
并同时保留原CodeQL命中被丢失、Scout发现被Review退回未决、以及外部LLM命中而本系统漏掉的反例。
VulnPy与GraphQL作为框架覆盖的正反对照，硬编码凭据与XSS作为单独分层，避免简单漏洞主导总体结论。

在看新实验标签前冻结这些机制假设、选择规则与失败政策。开发项目上的事后分析用于形成方法，
论文的确认性成绩需来自预留项目；模型/token/调用预算、CodeQL输入与查询套件、评分器和归一化应一致。
比较外部Agent时优先使用双方都有输出的项目，保存轮次与未完成状态；作者均值表只用于历史参照。

离线重新生成：

```sh
python3 benchmarks/experiments/analyze_realvuln_advantages.py \
  --evidence-root artifacts/research/realvuln/20261014-ablation \
  --output artifacts/research/verification/20261102-realvuln/advantages
```

本次分析的输入均先通过包清单哈希；六组原成绩此前已逐项目重算一致。
外部遗漏集合取所有保存轮次的命中并集，均未检出的金标另列；它不与均值TP相加，也不视为新的统一多轮得分。
