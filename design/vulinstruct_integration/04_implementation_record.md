# 实现与运行入口

| 位置 | 改动 |
| --- | --- |
| `system/contracts/src/semflow_contracts/security_specifications.py` | 冻结语料引用、截止日期、目标仓库排除条件、top-k、筛选门限和处理时限。默认缺省字段保持旧请求序列化。 |
| `discovery/specification_guidance.py` | 由实际代码标识符构造检索查询，复用原有语料和 BM25 适配器。模型载荷只含规范 ID 和通用陈述。历史 CVE 标识、语料版本、来源、分数、交集词和延时存入独立单元回执。 |
| `discovery/scout_inspection.py`、`scouting.py` | 在同一 Scout 模式内可选追加规范，并保留独立任务和源码证据。匹配不足、异常、耗时超阈值和上下文不足均留下状态。只有成功供给规范的候选标明规范增强模式。 |
| `discovery/review_pool.py` | 在已有源码页组装完成后按预算附上候选规范，保持源码引用与规范 ID 的命名空间分离。 |
| `discovery/review_obligations.py`、`review_verdict_gate.py` | 复用上一轮源码义务和缺口调度。可选的策略 4 为排除追加独立语义反证要求。没有反证的 `excluded` 保留未决。历史 API 仍用 `excluded` 键。消融结果将策略 4 中有反证的该值映射为 `refuted`。 |
| `app/research_bridge` 与 `research_cli` | Web 请求和独立 CLI 都可携带同一冻结策略。没有新的 Web 服务、表或任务队列。 |
| `system/scripts/benchmarks/vulinstruct_matrix.py` | 冻结 A–F 参数、共享同一源码快照并确定运行顺序。执行需显式开启，收据按原执行 ID 读取或继续。 |

首次真实 CodeQL 导入暴露了暂存路径超出 Windows MAX_PATH 的问题。归档文件本身通过摘要校验。公共基线适配器使用 Windows 扩展路径做打包和同卷原子解包，并在回执中保留原逻辑路径。新增失败到通过的边界长度回归，继续校验归档摘要、成员路径、体积和符号链接。

## 使用方式

1. 将已公开 Parquet 转换为仅含通用约束的 `CorpusDocument` JSON 数组。真实数据转换工具与查询回执保存于 D 盘实验目录。
2. 在确定的科研根目录运行 `semflow-research discovery-freeze-specifications --root <科研根目录> --documents <JSON数组文件>`，得到冻结语料 JSON。Web 任务的语料应冻结在平台的 `ARTIFACT_ROOT/research` 内。
3. 在 Scout options 或 Web Scout 请求加入 `security_specifications`，其下设置 `corpus`、`as_of`、`excluded_repositories` 及可选的相关性预算参数。无需设置 CWE。关闭时省略该字段。
4. 现有 `discovery-scout`、`discovery-discover` 和统一复审继续使用原入口。需要启用独立排除核验时，将复审配置 `strict_refutations` 设为 `true`，CLI 复审使用 prompt 12 和 evidence_navigation。

## 适用限制

语料软时限用于识别词法查询超时并回退。运行中的单次内存 BM25 不进行进程级中断，输入文档上限为 1,000。相关性是排序和字词门限，不能解释成概率。当前真实数据投影只包含历史来源和通用陈述，具体历史根因、补丁和解法未进入模型载荷。新复审策略的独立反证仍依赖已有的局部行为验证器，复杂跨函数授权或框架语义会出现更多未决。CodeQL 查询规则、自动修复和规则生成沿用原有内核。
