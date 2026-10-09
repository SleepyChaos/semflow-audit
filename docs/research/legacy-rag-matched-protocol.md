# 在旧 RAG 测试集上比较当前方案

日期：2026-10-04。运行前冻结协议；运行后的检索模式偏差及修正追加在第 5 节，原实验产物保留。用户要求对照截图中的旧 RAG 成绩；本次主对照选择旧方案最强 K 组，不用旧默认失败组替代。

## 1. 任务与评分保持一致

- Python / JavaScript × eval / SQL / XSS，共六个独立语义任务，每组每任务三轮，18 次请求；重复轮次不算独立漏洞。
- 直接读取旧 `rule-ablation-b7077f7e-6895-4fdc-af7a-60a6a9f248e7/holdouts/*/dataset.json`，校验与旧源码/当前变换器完全相同。隐藏正反例、文件名、行偏移、别名、遮蔽、安全操作和位置金标保持不变。
- 使用原位置集合 expected/actual 评分器。生成/编译、开发正反例、隐藏检查、端到端分别报告；所有请求进入分母，执行失败不当作安全结果。
- 端到端通过要求完整生成、开发检查和隐藏正反例均通过。精确率/召回率仅对实际完成隐藏执行的规则报告，并同时报告执行覆盖率。
- 旧截图 A–F/K 成绩作为历史参考；主结论来自此次重新运行的 old_K 与真实 auto new_v6（旧控制引用规则见第 5 节），不将不同时期成绩假装成同步对照。

## 2. 对照方案

| 组 | 生成方案 | 检索材料 | 源码理解/验证 |
|---|---|---|---|
| old_K | 旧 v3 受限 DetectorSpec＋固定官方模板＋完整候选反馈＋开发执行 | 重用旧 K 对应任务/轮次当时的冻结检索输出，不重新访问已扩充公共库 | 原先不主动读取源码；使用当前共同任务基线 |
| new_v6 | 当前默认 v6，自由 QL/必要模型、双集合角色路由、完整候选及执行反馈 | 冻结当前公共库的 document allowlist，默认 auto 检索（可回退 BM25） | 实际开发源码、分层解释、只读取证、原项目单规则执行 |

双方使用相同旧 requirement、用途、策略、固定依赖、模型参数和同一任务的基线。为满足当前必需源码契约，每个任务使用原公开微样例的一个普通处理函数作为开发项目，移除 target 标签；不提供改名/行偏移后的隐藏源码、别名/安全反例或评分金标。旧方案保持不读取源码的行为，新方案使用其新增能力。

这是整条方案比较：资料扩充、源码读取、输出形式和验证都发生变化，不能将差异单独归因于 RAG 或 embedding。旧 K 的官方模板是有效强基线；已有模板检出不作为 AI 新增漏洞覆盖。

## 3. 固定运行条件

- 沿用旧协议：实际请求模型 `deepseek-v4.1-flash`，thinking disabled，temperature 0，单次初始输出预算 **6000**（当前产品默认 8000 本次不用），最多两次候选。
- 同样的阶段上限：24 次实际模型请求、100000 tokens、300 秒模型阶段预算、90 秒请求 timeout；SDK 有限恢复继续计入。新方案额外受既有语义取证预算限制。
- 固定 CodeQL CLI 2.23.5 与原 packs。保留旧 v3 prompt SHA256，冻结当前 v6；前后校验材料、向量、提示词和评测 hash。
- 并发 2，按 case 分配 Worker；同一 case 的原项目和隐藏数据库串行使用，避免动态查询缓存或数据库锁竞态。每轮随机化两组顺序，随机种子 20261004。
- 使用已有隐藏数据库且实际查询 `--rerun`。不声称冷启动或严格性能因果；生成、额外原项目复测、隐藏评价、调用/token 单列。
- 创建禁用研究账号与独立任务，保留原始产物，不批准或发布规则，不做 GUI 测试。历史实验文件不覆盖。

## 4. 运行与交付

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.legacy_rag_comparison
# 已完成请求不会重复生成；未完整提交的请求必须先核实，不静默重跑。
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.legacy_rag_comparison --resume
```

产物：`artifacts/benchmarks/legacy-rag-matched-20261004/` 的冻结 manifest、资料/检索记录、开发源项目、逐请求 stage/调用/失败/规则、隐藏 SARIF 和报告。提交的汇总不包含密钥、实际向量或私有上传项目。

最终报告需给出逐任务结果，并单列已知的 Python Flask `@app.get` XSS 覆盖缺口、模型/材料/预算失败；不改样例来追求满分。若效果退步，同样记录。协议偏差另记，已完成候选不因看到隐藏结果而重新生成。

## 5. 实际执行偏差与修正（运行后追加）

首次输出 `legacy-rag-matched-20261004` 的新组被脚本设为 strict hybrid，虽然协议原先称当前默认；产品默认实际为 auto。首次 36 次请求完整运行，所有负面成绩保留，偏差写入原目录 `protocol-deviations.json`。没有改提示词、生成器、资料或隐藏金标来优化已知测试结果。

随后将实验模式修正为实际 auto，复用完全相同的 18 个已完成旧 K 控制、原任务、源码基线和冻结身份，再追加 18 次新请求：

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.legacy_rag_comparison \
  --output artifacts/benchmarks/legacy-rag-deployed-20261004 \
  --reference-run artifacts/benchmarks/legacy-rag-matched-20261004
```

旧控制复制记录具有 `reference_record`，不重新调用模型，不重复算测试数量。实际共 54 次新生成请求；auto 与旧控制是顺序组，不能假装同期随机交错，更不能据此作严格速度因果推断。脚本后续默认 auto；原 strict 组仍单列为偏差实验，不与 auto 的 18 次混合。

结果见[原测试集复测报告](legacy-rag-matched-results.md)。预算仍沿用旧 6000，未测产品完整默认 8000 配置。
