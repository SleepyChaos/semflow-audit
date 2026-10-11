# 测试结果、环境与版本归档

整理日期：2026-10-09（北京时间）。当前归档：**`20261009-workspace-v3`**；旧归档 **`20261009-workspace-v1/v2`** 保持不可覆盖。

当前源码内容版本：**`WORKSPACE-1e56fb9a3b078ae5`**（509 个代码/测试/脚本/锁定配置文件）。已归档 **47 份报告/汇总＋1184 份本地结果/配置/日志收据**，共 1231 个文件；文件数量不等于独立实验或通过数量。本轮单列 **VALIDATION-10-CHAIN-COMPLETION**，87 份文件；前一批 **VALIDATION-10-SUPPLEMENT** 保持原结果。

[各链路最新测试情况与用途](../research/chain-completion-20261009-results.md)：全量230项及新增3项归档保障通过，累计233个不同测试；两语言4个真实Scout和2个Review完成，22次调用。真实修复、知识索引、规则批准/发布/再用、最终报告页面流程尚未完成；脚本失败留存，自动审批服务额度阻塞继续执行。临时测试服务已停，自己的账号与checkpoint保留供恢复。**不能声明全部链路通过。**

[上一批默认能力补测](../research/supplemental-20261009-results.md)：96例平台P73.33%/R68.75%/F1 70.97%；Repair1 10/10、Repair2 9/10；旧规则候选15/18；有效GUI10/11，手机退出入口仍失败。这些不同用途的结果不与本轮流程计数相加。
这里按项目功能改进版本和补充验证批次统一归档。历史报告、成绩和原始失败记录保持原样；实验状态及当前索引增量更新。旧报告中的“当前”“默认”仍指原报告时间，不能用今日默认配置补填历史版本。

## 查询入口

- [仓库论文库](../../benchmark-data/papers/README.md)、[测试数据包与恢复](../../benchmark-data/datasets/README.md)、[测试集原始说明](../../benchmark-data/dataset-notes/README.md)：此前桌面资料与本地研究材料的仓库入口；研究数据发布副本的过滤不改变历史测试成绩。
- [项目测试方案说明·Word 当前版](项目测试方案说明_v2.2.docx)：说明版2.2，对应测试方案v7；恢复说明版2.0的详细正文，竞品功能范围表和模块对照表沿用说明版2.1的内容、列宽与排版。共11页，全部采用相同的A4纵向尺寸和页边距。核对记录见[当前文档收据](project-test-plan-explanation-v2.2.receipt.json)；不是测试完成记录。
- [Word说明版2.1](项目测试方案说明_v2.1.docx)与[原文档收据](project-test-plan-explanation-v2.1.receipt.json)保留；其原始正文见[v6归档副本](simple-three-module-test-plan-v6.md)。
- [Word说明版2.0](项目测试方案说明_v2.0.docx)与[原文档收据](project-test-plan-explanation-v2.0.receipt.json)保留；其原始正文见[v5归档副本](simple-three-module-test-plan-v5.md)。
- [Word说明版1.2](项目测试方案说明_v1.2.docx)与[原文档收据](project-test-plan-explanation-v1.2.receipt.json)保留；其依据的原始内容见[v4.2归档副本](simple-three-module-test-plan-v4.2.md)。
- [Word说明版1.1](项目测试方案说明_v1.1.docx)与[原文档收据](project-test-plan-explanation-v1.1.receipt.json)保留；其依据的原始内容见[v4.1归档副本](simple-three-module-test-plan-v4.1.md)。
- [Word说明版1.0](项目测试方案说明_v1.0.docx)与[原文档收据](project-test-plan-explanation-v1.receipt.json)保留；其依据方案的原始内容见[v4归档副本](simple-three-module-test-plan-v4.md)，保持原文件哈希。
- [项目完整测试方案·静态页面](project-test-plan.html)：可离线打开的HTML展示，含三个模块完整正文、目录导航及打印布局。
- [项目完整测试方案](simple-three-module-test-plan.md)：与Word当前版一致的方案正文；明确RealVuln 26项目、OWASP 1230例、PatchEval 1000任务/230动态任务，以及QLCoder完整176项Java CVE配对任务的范围、评价目标、论文对照和竞品功能范围。
- [测试方案资料索引](test-plan-reference-index.md)：正式基准论文、测试集与竞品官方材料的来源编号；桌面资料包按用途收录对应论文和文档。
- [项目测试历史结果附录](project-test-status-appendix.md)：原合并方案中的历史成绩及其局限；小样本结果不替代完整方案验收。
- [本轮真实链路补测归档](20261009-workspace-v3/improvements/VALIDATION-10-CHAIN-COMPLETION.md)：已完成、失败和未评估分列。
- [前一批新样本补测归档](20261009-workspace-v3/improvements/VALIDATION-10-SUPPLEMENT.md)：成功、失败、unknown、未评估和全部先前尝试。
- [旧 workspace-v2 登记册](20261009-workspace-v2/registry.json)：500源文件、1144份结果冻结。
- [旧 workspace-v1 登记册](20261009-workspace-v1/registry.json)：491 源文件、708 份历史结果冻结；后续只做副本校验，不改写。
- **[按项目改进版本归档](20261009-workspace-v3/improvement-index.md)**：主要入口。IMPROVE-00～10 分别对应基础原型、三项首轮改进、候选反馈、模板QL、语义修复/双库、RAG稳定化、双引擎、复核覆盖、业务输入覆盖、语义隔离与当前默认能力；每个版本有独立文档。
- [逐文件结果索引](20261009-workspace-v3/result-index.md)：每份报告、机器汇总与本地收据的结果 ID、内容哈希和版本关联。
- [历史内容版本索引](20261009-workspace-v3/version-index.md)：配置、实现、Prompt 哈希收据对应的 VER 标识。
- [机器登记册](20261009-workspace-v3/registry.json)：完整 SHA-256、原始字段路径、同批配置、复用关联与缺失引用。
- [当前环境快照](20261009-workspace-v3/environment.json)：实测工具版本、已安装/锁定依赖、非秘密配置、Prompt 哈希和本地镜像 ID。
- [测试类别和后续计划](../../benchmark-data/test-programs/README.md)：双引擎代码审计、代码修复、规则生成，按功能→意图→材料类型分类；计划条目不是已完成成绩。
- [已收集测试结果的分类与用途](../../benchmark-data/test-programs/collected-results-classification.md)：将主要历史测试系列关联到三级分类及原改进版本；冻结归档保持原样。

归档边界是结果报告、汇总、阶段结果和关键身份收据，不是整个 `artifacts/` 的完整备份。真实上传源码、完整 CodeQL 数据库/SARIF 目录、逐请求输入输出和语料正文仍在原来的忽略目录中。本轮公开/合成输入、评分材料的 input-source.tar.gz 另有本地冻结副本；新增选定日志、JUnit、截图及清理收据也已保存，不进入公开登记册正文。后续备份工作区时需要一并保留这些目录。本轮增加真实下载SARIF和各尝试runner冻结副本；凭据排除。workspace-v3使用离线环境观察，不访问Docker镜像服务，镜像身份明确标记not_observed；不能继承旧归档身份冒充当前观测。

IMPROVE 编号是本次按 `docs/` 功能改进边界建立的内部归档名，不是新发布的 Git tag。当前默认能力归入 **IMPROVE-10**；本轮 **VALIDATION-10-SUPPLEMENT** 仅补充验证，不声明新增产品改进版本；Astroid revision-02 实验单列 **EXPERIMENT-10-ASTROID**，共享工具环境和未能核实改进归属的结果另列。分类规则保存在 `scripts/test_archive/improvement-versions.json`，不按文件时间或单个 Prompt 的 v 数字猜测。

每组包含该轮改进的验证以及其旧版本对照。旧版对照保留原组别和实现收据；例如语义版对旧K、OWASP48 revision-01对base，不能因为比较发生在新一轮就把两组都归为新实现。跨版本累计结果在版本文档中明确写出实际组成。

## 统一标识

| 标识 | 含义 | 使用方式 |
| --- | --- | --- |
| `20261009-workspace-v3` | 本次归档批次 | 归档目录不可覆盖；后续变化创建新批次 |
| `WORKSPACE-…` | 本次代码、测试、脚本、锁文件的内容版本 | 完整文件清单与源码压缩包在本地归档；不是应用的 `0.1.0` 包版本 |
| `RES-…` | 原结果路径的稳定 ID | 同一个文件更新后 ID 不变，SHA-256 必须变化，因此引用必须同时携带归档 ID 和内容哈希 |
| `VER-…` | 含哈希证据的历史收据内容身份 | 收据可证明实现、Prompt 或语料中的某部分；不能一律当成完整代码发行版 |
| 原 `run_id` / `experiment_id` / StageRun ID | 原始实验/阶段身份 | 保留旧命名，结合结果 ID 和原字段定位；不同目录中的 v1/v2 不混用 |

结果引用格式：**归档 ID + RES ID + 完整 SHA-256 + 原批次/版本收据**。例如报告只写“v8 测试通过”不足以定位，需要同时说明它是规则 v8、哪个实验批次、哪个任务集和预算。

登记册中 `version_receipt_ids` 只绑定最近的同批 `config.json`、`manifest.json` 或 `identity.json`；`related_result_ids` 还可能包含旧对照、失败诊断和复用结果。`test_version_ids` 表示相关哈希收据集合，组合报告可能有多个 VER，不能选一个代替全部。

`version_status` 描述文件自身保存的证据：`hash_evidence` 有部分内容哈希，`declared_only` 只有版本/模型等声明，`unresolved` 没有可抽取的版本声明。Markdown 报告可能自身为 unresolved，但能关联到明确配置；看关联收据后再判断。任何一种状态都不自动证明测试成功、标签无暴露或完整可复现。

## 各改进版本的历史测试口径

正式分类以改进版本目录为准；下表补充各测试系列的阅读口径。精确文件哈希和原始身份以逐文件登记册为准。时间相近、使用同一个模型别名，均不意味着代码、输入、预算或评分相同。

| 时间 / 测试系列 | 批次与版本口径 | 结果入口 / 已有结论 | 防混淆边界 |
| --- | --- | --- | --- |
| 10-03 基础回归与静态基准 | 原始 UUID 批次；报告记录 CodeQL 2.23.5、Py pack 1.6.0、JS pack 1.4.0 | [基础结果](../research/benchmark-results.md)：50 普通测试、1 集成通过；包含独立微样例、外部 oracle 和规则 holdout | 集成模型为替身；早期实现未完整冻结，不能归为今日版本 |
| 10-03 真实模型首测 | `live-model-859c5f0f-a059-4d79-acd5-6f00712628d9` | [真实模型结果](../research/live-model-results.md)：30 阶段尝试，27 完成、3 失败 | 仅 smoke 核对实际响应模型；当时没有 embedding，不能套用当前混合检索配置 |
| 10-03 M1/M2/M3 | `phase-one-f143a708-97fc-4290-976d-f6d9a984fb0f` 及后续分项收据 | [第一阶段](../research/phase-one-test-results.md)：67 普通测试、1 集成通过 | 各子实验、规则验收、thinking/library 对照分别保留 |
| 10-03 第二阶段 | 按 Flask baseline/live、real-pair 等 UUID 区分；实验 rule5/review3 | [第二阶段](../research/phase-two-results.md)：87 普通测试、2 集成排除，真实链路另测 | 排除项不能计入通过；实验 Prompt 与当时默认 Prompt 分开 |
| 10-03 规则消融 | `rule-ablation-b707…`、`framework-ablation-2a29…`、`dev-feedback-ablation-6c57…` | [消融报告](../research/rule-generation-ablation-results.md)及对应 manifest | 动态查询缓存修正前评估已作废；使用保存的修正后结果，不选旧分数 |
| 10-04 语义修复与规则 | 基线声明 `2b1519b`；repair1/2、rule2/6；多份 semantic 控制批次 | [语义开发结果](../research/semantic-development-results.md)：规则单案例 0/3→3/3、修复 6/6→6/6 | baseline_commit 不是所有未提交实验代码的身份；重复轮次不是独立漏洞 |
| 10-04 旧集匹配复测 | `legacy-rag-matched-20261004`、`legacy-rag-deployed-20261004` | [旧集复测](../research/legacy-rag-matched-results.md)：旧 K 15/18、v6 默认 auto 1/18 | 与上述单案例 3/3 是不同任务集；共同输出预算 6000 |
| 10-04 RAG 语料 v3/v4 | `rag-corpus-v3`、`rag-corpus-v4` 与固定上游 commit | [v3](../research/rag-corpus-expansion-v3-results.md)、[v4](../research/rag-corpus-expansion-results.md)：130 官方开发测试通过、8 仅编译通过、3 失败排除 | 语料版本不同于规则 Prompt 版本；可用性不同于准确率 |
| 10-04 规则稳定化 | `rag-stabilization-20261004`（v7）、`rag-stabilization-v8-20261004`（v8） | [稳定化](../research/rag-stabilization-results.md)：完整 v8 15/18 | 第二轮旧 K 复用第一轮；外部 source 的 8000 输出预算另列 |
| 10-05 双引擎开发 | 最终 `dual-discovery-final-20261005`；前三轮保留诊断 | [双引擎开发](../research/dual-engine-development-results.md)：六个自建案例，支持正例 1/3 | 输入入口修订、失败反例和实验后修复不能混成新一轮准确率 |
| 10-05 首轮校准 | `20261005-calibration-v1`；冻结 scout1/review4/rule8/repair2 | [校准结果](../../benchmark-data/experiments/calibration-results.md)：99 文本调用，正式门槛未完成 | config 同时保存 git_head 与工作树哈希；旧 loader、Bandit 解析失败结果保留诊断 |
| 10-05 发现整改 | `discovery-retest/20261005-v1`、最终 `20261005-v2`；scout3/review6 | [同池复测](../../benchmark-data/experiments/discovery-retest-results.md)：59/59 候选复审完成，补充支持 4 主根因 | 原静态结果和候选池复用；新 Scout 单列，不把候选变化混入配对 |
| 10-06 输入/覆盖整改 | `discovery-coverage/20261006-v1…v6`；最终 Scout5/Review7 | [覆盖结果](../../benchmark-data/experiments/discovery-coverage-results.md)：24/31 暂定支持根因 | v2 粗筛＋v3 补读＋v4/v5 复审＋v6 单次补测，是组合版本；扩大输入与预算 |
| 10-07 语义整改 | `discovery-semantics/20261007-v1…v7`；Scout6/Review8 | [语义结果](../../benchmark-data/experiments/discovery-semantic-results.md)：累计 29/31 | v3 有效历史与 v4–v7 定向补测合并，不能称新版本单次全扫 |
| 10-07 OWASP56 | `owasp-discovery/20261007-pilot-v1`；Scout6/Review8；seed20261005 | [56 例结果](../../benchmark-data/experiments/owasp-discovery-results.md) | AI 56 例与静态全量 1230 例不互相替代；105 项安全任务 unknown |
| 10-07 机制泛化复核 | `discovery-generalization/20261007-host-replay-v1` | [机制复核](../../benchmark-data/experiments/discovery-generality-review.md) | 历史暴露样例和变换回放，不是新模型端到端发现验收 |
| 10-07—08 OWASP48 开发 | `owasp48/20261007-evolution/runs/{base,revision-01,revision-02}/development-*` | [最终比较](../../benchmark-data/experiments/owasp48-final-comparison.md)的开发表 | 两个开发集分开；revision-02/Astroid 实验不充当最终候选 |
| 10-08 OWASP48 验收 | 同一总批次，`base/acceptance-01` 对 `revision-01/acceptance-01`；seed2026100748 | [48 例验收](../../benchmark-data/experiments/owasp48-final-comparison.md)：新平台 TP18/FP2、P90%、R75%、F1 81.82% | 候选在计分前选定；已暴露、今后仅回归。OCR 为真实竞品，未统一盲审；不是全部告警准确率 |
| 10-09 新样本补测 | `supplemental/20261009-v1`；Scout7/Review9、Repair1/2、历史full_v8规则 | [新增结果](../research/supplemental-20261009-results.md)：96例平台F1 70.97%，修复10/10与9/10，规则15/18，GUI10/11 | 文件级新OWASP同分布验证；修复/规则为自建且未人工审核；未改生产代码，失败完整保留 |
| 10-09 迁移复核 | Git 基准 `58d2c8f7ba16d6e2517b1855db593bc8377ec7bd` | [迁移复核](../workspace-migration-review.md)：选定行为测试 43 passed | 这是原文记录；没有本轮完整环境/原始日志，不能称完整运行收据 |

其他本地报告、失败、子任务和费用/完整性收据也在逐文件索引中。原报告内的绝对旧路径在登记时映射为工作区相对路径，原文件本身没有改写。

## 当前环境归档

当前 HEAD 是 `58d2c8f7ba16d6e2517b1855db593bc8377ec7bd`，归档前存在未提交文档及本次归档脚本/测试。以源码清单的内容哈希作为当前 WORKSPACE 身份，不能仅凭 HEAD 假设干净工作树。

| 层次 | 当前观察 / 固定身份 | 归档方式 |
| --- | --- | --- |
| 系统 | macOS 15.7.2 / arm64 | environment.json 的 platform / architecture |
| 后端运行时 | Python 3.14.6 | 当前解释器版本和路径；完整 installed_python_packages |
| CodeQL 抽取器 | Python 3.11.15 | 实际执行 `python3.11 --version`；不与后端 Python 混用 |
| CodeQL | CLI 2.23.5；Python queries 1.6.0、JS queries 1.4.0 | CLI build 信息、配置和原批次 suite/pack 收据 |
| 后端核心框架 | FastAPI 0.141.1、LangGraph 1.2.12、Haystack 3.3.0、SQLModel 0.0.39、OpenAI SDK 3.24.0、Astroid 4.3.3 | 根 uv.lock 完整 SHA-256，锁定清单与安装清单分别保存 |
| 前端 | Node v26.0.0、npm 11.12.1；React 19.3.0、Vite 8.3.2、TS 6.0.3、Playwright 1.62.1 | package-lock.json 完整 SHA-256；四个已安装核心包版本单独核对 |
| 工具 | uv 0.11.2、pytest 9.1.1、Ruff 0.16.4、Docker 29.5.2 | 实测版本；不是历史测试环境的推定值 |
| 阶段默认 | Scout7 / Review9 / Repair2 / Rule8 | 读取当前 API 创建阶段的源码；独立 Prompt 文件逐一哈希 |
| 模型与检索 | 请求别名 deepseek-v4.1-flash；thinking disabled；embedding 模型/修订/维度另存 | 仅白名单配置；别名不保证服务商后端版本，历史响应模型以原收据为准 |
| 服务/验证镜像 | pgvector:pg17、Redis 7.4.2-alpine、Python validator、Node22 validator | 本地 image ID、RepoDigest、架构；没有把标签当不可变身份，也没有重启服务 |

本轮使用现有数据库做隔离回归和专用 GUI 合成夹具，并临时启动当前 API/Vite；没有核查全量数据库内容、迁移应用状态、原有 Worker 进程配置或重新冻结当前 RAG 语料。历史语料只能使用对应冻结批次的 corpus_hash 和 manifest；锁定依赖与源码可重建环境，但没有把完整虚拟环境或 Docker 镜像层复制成离线安装包。

## 本地归档与检查

本地不可覆盖副本位于 `.local-workspace/test-archives/20261009-workspace-v3/`，受既有 Git 忽略规则保护：

| 文件 | 用途 |
| --- | --- |
| `workspace-source.tar.gz` | 当前代码、测试、脚本、锁文件和非秘密配置源码快照；不含真实 `.env` |
| `implementation.json` | 快照中每个文件的完整 SHA-256 |
| `receipts/` | 报告和关键本地结果按原工作区相对路径保留逐字节副本 |
| `by-improvement/` | 每个项目改进版本独立的结果清单，指向对应冻结副本；跨组关联保留原引用 |
| `archive-checksums.json` | 对公开索引、环境 JSON、源码压缩包和全部收据副本做完整性校验 |
| `completion.json` | 只有原件/副本/源码快照校验通过才生成的完成收据；缺失即未完成归档 |

归档脚本仅执行版本查询和已有镜像的只读检查，不启动数据库/目标服务、不运行扫描或模型请求。关键身份只从明确字段提取，模型输入、上传源码、金标、密钥及报告全文不写入可提交登记册。公开文档和 JSON 是整理后的元数据，完整原始收据留在忽略目录。

在项目根目录检查本次归档与原结果是否一致：

```sh
.venv/bin/python scripts/archive_test_results.py verify 20261009-workspace-v2
```

如原结果已按后续工作更新，只检查冻结副本：

```sh
.venv/bin/python scripts/archive_test_results.py verify 20261009-workspace-v2 --archive-only
```

后续归档必须使用新 ID；禁止修改旧目录或删除已有结果后重用旧 ID：

```sh
.venv/bin/python scripts/archive_test_results.py create YYYYMMDD-workspace-v2
```

脚本非零退出表示归档/校验失败。JSON 损坏会作为 failed 解析状态登记；结果版本缺失不会补成今日版本；原结果/副本被修改会给出具体路径。归档校验通过只证明保存一致，不等于其中每项审计或能力测试通过。

## 新实验必须保存的身份

每个新实验在执行前创建独立 run_id；记录 Git HEAD、未提交实现文件哈希、源码输入清单、依赖锁哈希、CLI/pack/suite、阶段 Prompt/图/runner/评分器身份、模型请求与实际响应版本、预算/seed、语料与 embedding 身份、任务划分及暴露状态。执行后分别保存完成、失败、unknown、未评估、复用来源和实际费用/时序收据，再创建新的工作区归档。

旧测试只声明版本、没有完整实现/环境冻结时，保持“仅声明 / 无法完整追溯”；不能通过当前文件、文件修改时间或某次 Git 提交推定旧运行版本。OWASP48 已暴露验收和累计 29/31 的组合结果尤其不能重新命名成新版本独立验收。

本轮验证：33 项可靠性回归、5 项新增评测数据/归档测试通过；9 项归档测试另行重复核查，与前者有重叠，不相加。Ruff 检查/格式检查通过。归档验证覆盖版本隔离、歧义拒绝、内容变化、缺失/损坏证据、密钥排除、禁止覆盖和副本篡改；冻结创建逐字节核对原件/副本及源码压缩包成员。真实模型和浏览器结果按新增报告单列，归档校验通过不覆盖其中失败。
