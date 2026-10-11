# v7 稳定化对照与消融协议

2026-10-04；实验前定义。关联 [阶段计划](../../design/rag-stabilization-phase-plan.md) 与 [旧测试协议](legacy-rag-matched-protocol.md)。

## 数据与隔离

复用原 Python/JavaScript × eval/SQL/reflected-XSS 六类需求及原隐藏变体，每类三轮。隐藏源码、行号标签及六个 hash 均不改变，不进入模型/RAG，也不用于失败后的修改。重复次数不是独立漏洞数，不计算依赖独立性假设的显著性。

新库为 271 个固定版本参考来源和 141 个完整查询范例的当前版本；执行失败条目排除。官方开发例可用于检索，不能同时充当独立评估。最终语料 ID/正文/元数据/向量身份、CLI、模型配置、提示词与实现 hash 在开始前冻结。

## 组别

| 组别 | 相对完整 v7 的变化 | 请求数 |
|---|---|---:|
| old_K | 新跑旧 v3：冻结旧检索结果、受限规格、官方模板、开发执行反馈 | 18 |
| full_v7 | 精简上下文、取证反馈、双库当前版本、auto 检索、受限规格及真实执行门槛 | 18 |
| no_compact | 保留完整冗长元数据输入，关闭精简 | 18 |
| free_ql | 关闭受限规格，其他流程一致 | 18 |
| no_progress | 关闭重复读复用和进度反馈，保留相同 v7 提示词 | 18 |
| bm25_v7 | 关闭向量检索；必要 API 声明槽位在各 v7 组均使用确定的词法符号检索 | 18 |

共 108 个新请求。六类任务按固定随机种子打乱，两个工作线程；同一任务的组别交错执行，同一原项目/隐藏数据库不并发修改。旧 v6 1/18 作为先前的回归观察，正式 old_K 对照重新执行。

## 预算与指标

继承旧 K 冻结预算：输出 6000 tokens、温度 0、关闭 thinking、阶段 24 次调用/100000 token/300 秒、接口超时 90 秒、两次候选。结构恢复使用同一 provider 策略；无隐藏评估反馈循环。

统计所有请求的端到端成功、编译、开发执行、隐藏执行及各失败阶段。TP/FP/FN 同时给出执行条件；未生成不能作为“无漏洞”。单独报告成功请求中位耗时、模型调用、输入/输出 token。embedding 调用不计入 chat token 数，检索耗时包含于阶段总时间。

完整 v7 与旧 K 是整体流程比较，不能归因于单一 RAG 组件。四组消融共享 v7 提示词、材料、角色和预算；取证反馈无收益也必须报告。缓存和局部小样本限制速度与泛化结论。

另做外部 API 开发及评估：三轮事件 API source 扩展，生成后增加导入别名/辅助函数传播与数值转换、常量、不同 API、遮蔽调用安全反例。数据手写，不冒充标准基准；规则版本完成后才进行额外评估，结果不反馈模型。

## 复现

```sh
PYTHONPATH=backend:scripts .venv/bin/python scripts/validate_expanded_corpus.py
PYTHONPATH=backend:scripts .venv/bin/python -m scripts.benchmarks.rag_stabilization \
  --output artifacts/benchmarks/rag-stabilization-20261004
```

中断必须 `--resume`，保留已完成请求和 started 标记。生成与评估记录分别保存；失败不自动补样本。实验不得中途修改实现、提示词或语料。


## 第二轮：v8 阶段边界与反馈修正

第一轮 108 请求保留，v7 full 12/18 未达到验收目标。开发日志显示取证阶段把后续 RAG 缺失当作 critical unknown，重复假设完整短文件仍有未读后文；自由 QL 重试把依赖日志和 pretty JSON 体积计入上下文门槛。v8 针对这些开发观察修正，没有依据隐藏数据增加框架/位置特判。

新实验 `rag-stabilization-v8-20261004`：full_v8/no_scope_context/early_rag/bm25_v8/free_ql 各 18 次新请求，共90；复用首轮全部18 old_K，记录 reference_record。相同模型、6000 输出、24调用/100000tokens/300秒、六类需求/开发源码/隐藏集。两worker按case串行、组间固定种子随机交错。代码、prompt、corpus/vector、CLI和隐藏集全部冻结；结束检查输入和实现哈希。外部API与覆盖检查可能同时占用本机资源，耗时结论限定于本次运行条件，不作纯算法加速推论。

no_scope_context 只去掉实际EOF/基线的准备上下文，保留v8 phase合同与事实门；early_rag 在inspect前取回相同双库并注入完整精简知识；BM25只改变检索模式，ApiGraphs精确声明槽在全部组均按固定BM25取回；free_ql取消受限规格，编译/开发/复跑门不变。因此不能把v7→v8跨轮变化解释为某个单一提示词因果效果。


## 冻结后的交付修正

第二轮108条完整记录（90新＋18引用对照）已通过结束时implementation/prompt/corpus/vector/CLI核验。之后修正三类非核心CWE角色槽位及NoSQL/存储/DOM的受限模板边界；不改变旧六类/SDK槽位调用，并通过普通兼容测试及20项产品路由复测。最终部署代码与实验代码的三文件差异保留专门receipt，原实验实现hash不重写。产品默认API版本8、6000预算，默认BM25/auto与冻结召回ID的12项对齐检查通过；最终真实集成验证默认API流程，不提供新隐藏数据给模型。
