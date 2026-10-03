# 规则生成原型与消融协议（2026-10-03）

## 范围与实现

本次验证论文方案的最小原型，未宣称完成 R1/R2 全部生产化：

- R0：完整候选在元数据/编译检查前保存；结构化诊断；v3/v4 反馈可携带上一版完整候选；确认缺陷的实际证据、摘要与不可变快照校验。
- 检索：固定 API 版本，按 Query / Customizations / AST 转换声明分路，精确符号过滤；仍使用真实 Haystack BM25，未宣称已配置向量检索。
- 受限规格：DetectorSpec 选择固定官方检测模板。模板来源、原始 SHA256 与 `baseline_reuse` 标识随规则保存，不算新增检测覆盖。
- 框架建模：FrameworkSpec 提取 Python 代码注入 sink 的导入模块、成员、危险参数索引；符号必须具有实际检索证据。确定性模板产生 `.qll`，复用官方数据流检测器。当前只支持 Python 代码注入 sink；未支持任意 source/summary/sanitizer 建模。
- 类型工具：固定作者 LSP 客户端 commit 和 npm lock，CLI 预检真实连接超时；不可用结果不作为类型证据。不得声称已经证明 LSP 消融有效。
- 所有规则继续停留在人工样例确认前。实验离线执行样例，不修改人工批准/发布状态。

GUI、HTTP 输入契约与默认 prompt v2 保持当前配置；v3/v4 与实验开关由内部基准脚本创建版本化阶段，避免把尚未验证的原型作为默认能力。

## 主实验：2×2 与规格对照

同一冻结语料、固定库版本、同一需求及模型策略；无模型模拟。

| 组 | 检索 | 编译反馈 | 输出形式 |
|---|---|---|---|
| A | 原始 BM25 | 日志 | 自由 QL |
| B | 分路检索 | 日志 | 自由 QL |
| C | 原始 BM25 | 完整上一版候选＋诊断 | 自由 QL |
| D | 分路检索 | 完整上一版候选＋诊断 | 自由 QL |
| E | 原始 BM25 | 完整候选＋诊断 | DetectorSpec＋官方模板 |
| F | 分路检索 | 完整候选＋诊断 | DetectorSpec＋官方模板 |
| 无 AI 基线 | 无 | 无 | 同版本官方模板直接执行 |

Python / JavaScript × eval / SQL / XSS：6 个语义任务，每任务每组 3 轮，108 次生成。重复测生成稳定性，不视作 18 个独立漏洞。固定随机种子 20261003 打乱顺序；并发 2。模型 thinking 全部 disabled、temperature 0、单次输出预算 6000，保留 M1 的统一阶段预算/有限恢复。

主组共用 v3 prompt 和完整 RuleResponse 契约；规格组按 DetectorSpec 契约输出，因此其 token/编译改善是整条受限规格路径的作用，不能归因为单个提示词。

评估数据从服务端微样本派生，修改文件名、变量/参数名和行偏移；不进入模型输入。这是同语义族的隐藏校准样本，不是跨项目泛化集。原有小型 holdout 已在前期研究使用过，不包装为全新外部 benchmark。

## 框架模型补充实验

3 种模拟导入模块，危险参数索引分别 0 / 1 / 2，实现不提供给静态分析器；每任务每组 3 轮，27 次生成：

- H：自由 QL＋分路 API 检索＋框架文档＋完整候选反馈。
- I：FrameworkSpec＋相同检索/文档/反馈＋确定性 sink 模板。
- J：I 移除领域框架文档，保留 CodeQL 查询、扩展与类型知识。
- 无 AI：官方代码注入查询，检验既有模型的覆盖缺口。

领域文档进入私有知识库；正反例不进入知识库或 prompt。独立反例包括安全常量，以及危险参数安全、用户数据仅流入非执行参数的调用。此实验是有明确定义语义的合成 API，不是现实 CVE 发掘。

## 度量与留痕

1. **可生成率**：所有请求为分母，完整结构/引用/样例语法/编译通过为分子。
2. **生成样例回归**：模型生成的正反例真正执行，而非只检查语法。
3. **隐藏样例准确匹配**：实际 SARIF 位置集合与预期集合比较，保留 TP/FP/FN。
4. **端到端成功率**：生成、生成样例回归、隐藏样例全部通过 / 所有请求。
5. **精确率/召回率**：只针对完成真实执行的检测器，单独报告执行覆盖率。失败不是安全、不是空扫描结果；不把未生成规则默认为无告警来伪造准确率。
6. **开销**：模型调用数、输入/输出 token、finish reason、阶段 wall time、独立执行时间。并发与工具缓存影响计时，只作本机描述；不能当作严格单线程速度提升证据。
7. **归因**：A↔B、C↔D 隔离检索；A↔C、B↔D 隔离反馈；C↔E、D↔F 检验整条受限规格路径；E↔F 检验规格路径检索增益；I↔J 检验领域文档的作用。

确定性重复的 query/modules/fixtures/dependencies 可复用已执行评估，缓存键保存。所有模型请求独立记录，失败与缺失也保留。

### 协议偏差

主实验运行期间准备框架 prompt 曾短暂改动 v3 文件。通过已记录的逐调用 prompt_hash 检出；受影响的完整请求保留到 `protocol-deviations/`，用原冻结 prompt 补跑对应配对格，单独报告额外调用。框架实验改用独立 v4 prompt。

框架独立样例最初硬编码预期第 7 行，但代码只有 6 行；真实执行前预检拒绝。修正至实际标记第 6 行后再评估，保留 `evaluator-errata.json`。没有改动源码或重新生成模型规则。

## 复现入口

```sh
.venv/bin/python -m scripts.benchmarks.rule_ablation --arms A_bm25_log B_routed_log C_bm25_candidate D_routed_candidate E_spec_bm25 F_spec_routed
.venv/bin/python -m scripts.benchmarks.rule_ablation --resume artifacts/benchmarks/<主实验目录>
.venv/bin/python -m scripts.benchmarks.framework_ablation
.venv/bin/python -m scripts.benchmarks.rule_ablation_devcheck artifacts/benchmarks/<实验目录>
```

依赖已有 `.env` 模型配置、数据库、固定 CodeQL packs；脚本不会打印密钥。实验数据均写入 Git 忽略的 artifacts，报告只提交汇总和协议。

### 真实工具验证发现的额外问题

- 相对 `log.parent/runtime` 加入 PATH 后，CodeQL 切换源码工作目录会使解释器别名失效，意外选择 Python 3.14。已把运行时目录改为绝对路径；失败数据库重建并核对 3.11 抽取日志。
- 独立样本的嵌套函数在插入行偏移注释时缩进被破坏；预检拒绝执行，改为保留原始缩进的正则变换后构建数据库。
- 最关键：同名 `audit/generated:generated.ql` 动态查询可复用同一数据库里上一条查询的 BQRS。已在动态查询执行时使用 `--rerun`，并增加真实 CodeQL 回归：同一数据库上依次执行 eval 与 int 两条查询，必须分别返回第 1、2 行。缓存修正前的独立评估作废、原样保留；只重跑工具评估，不重新生成候选来挑选结果。应用层仅允许以 query/modules/dependencies/dataset 完整哈希复用确实相同的评估。

## 补充：把真实生成样例执行纳入生成反馈

首轮发现编译成功与生成样例正确性存在差距，因此追加 27 次匹配实验，原首轮数据不删除：

- K：与 F 使用相同需求、私有语料、prompt v3 与模型策略；新增 `execute_dev`，每次候选编译后真实执行其生成正反例，失败的 expected/actual 与完整候选送回下一次生成。
- L：与 I 相同，prompt v4；同样加入真实生成样例反馈。
- 仍最多两次候选尝试，模型 SDK 恢复仍计入 M1 总预算，不允许独立 holdout 进入反馈。
- 这是补充实验，不伪装为先验注册结果。新增实际执行使阶段 wall time 增加；判断目标是端到端通过率，不是最快生成。
