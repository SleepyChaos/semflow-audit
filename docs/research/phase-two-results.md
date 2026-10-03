# 第二阶段首批改进与基准结果

2026-10-03。沿用 [总计划](phase-two-master-plan.md)，已完成工作包 A，并开展 B/C/D 的首批试验。正式论文规模的跨项目评价尚未完成。全部通过代码、API、CLI、CodeQL 和 Docker；没有 GUI 测试。机器可读汇总见 [phase-two-summary.json](phase-two-summary.json)。

## 1. 已落地的通用改进

- 规则生成拆为候选生成、契约/编译、开发样例执行、保存、人工批准和独立验收节点；编译或开发执行失败回到生成，最多两个候选。CLI 生成与任务入口使用同一实现。
- 每次候选保存输入、完整回复、诊断与内容摘要。模型回复完成后的节点重放复用已有候选；输入不一致或候选被修改立即失败。未完整提交的生成显式失败，保留产物。开发执行重放采用新目录，避免在已存在 CodeQL 数据库位置重建。
- 四条图链均记录节点耗时、完成/失败/取消/人工暂停状态；暂停等待不计入节点计算耗时。提库、查询、复审模型、取证、修复验证、规则编译/开发执行可以分别观察，尚未形成统一排队时间指标。
- 同阶段、同快照、同类型、同引用且同内容的证据复用 ID，避免重复写入和重复加入上下文；每次工具调用仍保留 trace。跨阶段、不同引用不复用，篡改缓存证据会失败。源码完整性检查仍执行。
- 新增实验提示词 rule v5、review v3。默认 GUI/HTTP 仍选择原提示词；新框架规格和新版复审先由研究脚本对照，未自动发布规则或改变人工结论。

普通回归 **87 passed、2 integration deselected**；最终真实四阶段集成 **1 passed，90.35s**；Ruff 与 diff 检查通过。集成中的模型是明确测试替身，只证明链路与暂停恢复。真实模型成绩来自下面的单独试验。

## 2. 研究依据与假设

IRIS 的 API 规格/上下文复审、QLCoder 的生成反馈支持减少自由 QL 生成并保留执行检查；相关读取记录见 [规则论文阅读](rule-generation-paper-review.md)。[SemTaint 2026](https://arxiv.org/html/2601.10865v1)强调针对潜在污点路径按需提取规格、核实摘要、复用规格。本项目暂未复现它的调用图修补。

[SastBench 2026](https://arxiv.org/html/2601.02941v1)的实验和负类构造提醒：工具取证未必优于固定上下文，近似 FP 不能直接当金标。因此本轮保留无工具对照，接受取证增加成本或导致误判的负结果。完整阅读范围与下一批真实基准见 [第二阶段文献核实](phase-two-literature.md)。

Flask 官方文档说明 [get/post](https://flask.palletsprojects.com/en/stable/api/)是 route 的方法快捷接口，始于 2.0；固定 python-all 4.0.10 的 Flask 模型只识别 route/add_url_rule。由此提出受限的路由模型扩展，再独立检验新增检出、反例和成本。

## 3. 规则生成与新增覆盖

冻结 12 个原创案例：6 个 XSS 正例、6 个负例，包含 Flask/Blueprint get/post、已有 route 控制、路由参数、转义、常量、纯文本响应、JSON 字典、同名无关接收器和未注册函数。样例是机制验证，独立任务仍只有一个框架 API 家族；不能视作 12 个真实 CVE。

实际 Flask 3.1.2 test client 验证 **12/12 标签一致**。JSON 字典响应为 application/json，未注册函数/无关接收器没有对应 HTTP 端点；检查不启动服务器或浏览器。运行时与依赖清单单独保留。

| 无 AI 对照 | TP / FP / FN / TN | 目标 P / R | 查询时间中位数 |
|---|---|---|---|
| 原生固定 reflected XSS 查询 | 1 / 0 / 5 / 6 | 100% / 16.7% | 5.30s |
| 人工指定正确路由扩展 | 6 / 1 / 0 / 5 | 85.7% / 100% | 5.33s |

三轮位置结果一致；人工模型首轮查询 23.86s，后两轮约 5.3s，首次编译影响明显。中位时间并不代表严格冷启动性能。

真实模型固定 `deepseek-v4-1-flash-260910`，thinking disabled、输出预算 6000，三种生成配置各重复三次。模型只获得框架/API 文档与需求；上述隐藏案例、运行时标签不进入生成。

| 配置 | 请求 | 生成/编译通过 | 隐藏全通过 | 生成阶段中位时间 |
|---|---:|---:|---:|---:|
| 分路 RAG＋完整反馈＋自由 QL | 3 | 0/3 | 0/3 | 16.82s |
| 同样证据＋受限路由规格/模板 | 3 | 3/3 | 0/3 | 7.93s |
| 受限规格＋真实开发样例反馈 | 3 | 3/3 | 0/3 | 26.23s |

六条规格产物均在隐藏例得到 **6 TP、1 FP、0 FN、5 TN**；带反馈三条的模型自生成开发样例也均执行通过。**JSON 误报使严格端到端通过仍为零。** 此结果说明受限规格稳定实现了路由覆盖，但编译和自生成样例不能保证响应语义正确。不能将 3/3 可编译写成规则成功率 100%。

这一新增覆盖属于 CodeQL 框架模型扩展；人工模型能够取得同样检测结果。AI 的贡献范围是从文档提炼受限规格和生成回归样例，尚未证明超越人工模型，也未完成项目 API 清单绑定。

## 4. 审计复审与成本对照

对人工扩展产生的同一批 7 条实际 CodeQL 告警进行四种复审配置，各三轮。其中 6 条是真阳性，1 条是经运行时证实的 JSON 误报。所有模型结论仍需人工决定。

| 配置 | 每轮真阳性保留 | JSON 误报排除 | 三轮模型调用 | 输入 token 合计 | 阶段中位时间 |
|---|---|---|---:|---:|---:|
| v2 固定上下文、无工具 | 6/6，三轮一致 | 3/3 次 | 3 | 15,409 | 4.74s |
| v2 主动取证（原配置） | 6/6，三轮一致 | 2/3 次 | 10 | 54,369 | 7.92s |
| v2＋证据去重 | 6/6，三轮一致 | 0/3 次 | 3 | 15,316 | 6.15s |
| v3 按缺失前提取证＋去重 | 6/6，三轮一致 | 3/3 次 | 3 | 15,705 | 5.28s |

新版提示词要求先识别缺失的审计前提；已有证据足够时直接给出结论，无法建立前提时保留 insufficient。它在本例减少调用并修正误报，但固定上下文对照仍更快。**去重单独使用没有改善语义判断。** 四组比较是小型顺序试验，候选 UUID、模型服务时延和回复仍存在波动；不能将工具调用减少全部归因为去重，也不宣称统计显著或普遍提高准确率。

以上 9 次规则生成请求与 12 次复审阶段共 **31 次真实模型调用**，输入 **182,589 tokens**、输出 **31,899 tokens**。失败也纳入成本。首次规则生成成本与后续扫描复用成本分别记录。

## 5. 真实材料与完整仓库基线

在任何扫描前冻结 20 项选择（每语言 10、每仓库一项），按 advisory ID 字典序降序选择；GHSA 不具有年份排序语义。该批是开发试点，不属于最后论文留出集。

完整 pre/post 快照已收集 **19 对**，含固定 commit、档案 SHA、源码数量与许可文件位置。CVE-2020-8205（Uppy）下载连续超时保留为失败，没有换成其他容易扫描的样本。Python pre 定义为给定 fix 的第一父提交，根因与 oracle 尚需独立核实。许可检查状态亦单独记录，材料保留在忽略目录。

首批按固定清单各语言前两项执行：react-draft-wysiwyg、browserslist、tornado、eduMFA，共 8 份完整快照。

| 项目 | 默认 2GB/2线程结果 | 提库 pre / post | 查询首轮 pre / post | 后续同库查询 |
|---|---|---|---|---|
| react-draft-wysiwyg | 两份查询均内存不足，提库完成 | 16.59 / 15.83s | 未完成 | 未完成 |
| browserslist | 两份均完成 | 5.59 / 4.64s | 18.58 / 19.29s | 约4.1–4.4s |
| tornado | 两份均完成 | 8.22 / 7.38s | 18.29 / 17.57s | 约4.4–4.8s |
| eduMFA | 两份均完成 | 15.23 / 15.15s | 39.43 / 38.43s | 约4.2–4.7s |

对两份失败 JS 数据库以显式 **4GB/1线程** 配置单列复测：均完成，首轮查询 51.75 / 58.24s，后续约3.8–4.9s。原失败保留在默认配置分母中；没有静默提高平台默认资源。

实际完成默认 18 次查询＋资源复测 6 次查询。固定查询的同库复扫可复用 CodeQL 正常缓存，不能把这些时间当修改后增量扫描，也不能恢复动态生成查询的身份缓存。OS 缓存未清除；部分采集、复审和集成在同机发生，计时属于描述性开发数据。

pre/post 告警总数分别为 react-draft-wysiwyg 2/2、browserslist 5/5、tornado 59/59、eduMFA 63/63。**相同总数不代表目标未修复；也不能将所有额外告警当误报。** Python 目前只有修复索引，OpenSSF 精确行标签只是探索性匹配。根因与独立 oracle 未完成，因此此表不给项目级 precision/recall。

## 6. 协议偏差、决定与下一批

- 首个人工路由模型漏导入 DataFlow，真实编译失败已保留；补全固定库明确导入后创建新实验目录。
- 材料解析器最初错误拒绝档案顶层目录；修复后以同一选择、同一版本重放已下载档案。初始与恢复日志保留；恢复启动时旧采集器尚在收尾，最终以恢复清单为准，后续禁止并行写同一 manifest。
- 新复审配置在原三轮后顺序执行，属于补充试验。正式性能测试应交替随机顺序、固定机器负载，不能用本轮宣称严格速度因果结论。

决定：保留图节点、计时、证据去重与恢复保护；受限路由规格、新复审提示词继续作为实验配置。下一批优先补**返回类型/MIME 与项目配置的证据约束**，避免为降低误报而全局添加宽泛 sanitizer；用跨文件、包装函数、自定义响应/JSON provider 的新案例验证安全边界。随后核实 19 对真实材料根因，补齐安全负例与双 oracle，再对真实告警扩展复审/主动发现比较。

速度下一步优先记录完整端到端/排队基线、同快照数据库复用与条件化证据预算；先解决资源可运行性，再做受质量约束的性能优化。当前没有实现完整增量扫描、通用 source/summary 生成或论文规模独立评价。

## 7. 原始产物与命令

- `artifacts/phase-two-tests.log`、`phase-two-final-integration.log`：87 项普通回归与最终真实集成。
- `artifacts/benchmarks/flask-baseline-56d72d5e-cb7c-41bb-a0ce-464b32ab55b2/`：冻结代码、原生/人工模型三轮 SARIF、runtime-oracle.json；初始编译失败在另一个保留目录。
- `artifacts/benchmarks/flask-live-a9f48831-e9cb-4055-8339-313e4fcdce3a/`：真实生成、固定/主动复审报告、selective-review.json、知识库与调用/节点记录。
- `artifacts/research-materials/phase-two-real-pairs-a19b0c08-0d41-47d2-a685-77e64d11fa43/manifest.json`：完整材料及失败历史。
- `artifacts/benchmarks/real-pair-pilot-ede5371c-6eb9-42c9-baeb-b3036301733e/`：4 个仓库基线和 resource-4096-1 复测。

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.flask_baseline
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.flask_live <flask-baseline-directory>
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.selective_review <flask-live-report.json>
artifacts/competitors/flask-oracle-venv/bin/python -m scripts.benchmarks.flask_runtime_oracle <oracle-output.json>
.venv/bin/python -m scripts.benchmarks.prepare_real_pairs --resume <material-manifest.json>
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.real_pair_baseline <material-manifest.json>
PYTHONPATH=backend .venv/bin/python -m scripts.benchmarks.retry_real_queries <pilot-report.json> --ram 4096 --threads 1
```

材料与模型输入保存在私有产物目录，不提交第三方源码、模型密钥或完整论文。复现实验需本机 CodeQL、固定查询包、测试数据库及已配置模型服务。
