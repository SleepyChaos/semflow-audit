# 当前项目目录索引与精简候选

扫描时间：2026-11-02T09:52:28.541221+00:00。源码基点：`6d86060`（审计修复已提交）。这是该时点本地工作区的只读盘点，含Git忽略内容；本文件和索引脚本随后单独提交。服务器未扫描、未清理。

## 1. 先看结论

工作区共 **5.79 GiB、251,521条文件记录**，其中Git跟踪1,175条、可见未跟踪181条。文件数包含符号链接与Git元数据，不包含空目录；体积为文件逻辑字节，不能等同释放磁盘空间。

主要空间来自`artifacts/`、`.local-workspace/`和Python/Node依赖。业务源码与文档的文件组织可以精简，但并不是磁盘占用的主因。**本轮没有删除、移动或压缩任何现有项目文件。**

建议顺序：先处理可再生成缓存，再核实环境用途，随后整理历史实验入口；原始证据、尚未验证可恢复的源码副本与数据包保留。

## 2. 目录用途与规模

| 目录 | 文件记录 | 逻辑体积 | 已跟踪文件 | 用途与建议 |
| --- | ---: | ---: | ---: | --- |
| `system/` | 49,159 | 1014.40 MiB | 704 | 运行系统、测试、脚本；保留，依赖和产物另算 |
| `benchmarks/` | 17,722 | 452.39 MiB | 326 | 评测协议、数据包、报告及展开输入；保留正式来源，归档旧轮次 |
| `design/` | 64 | 8.10 MiB | 44 | 架构、模块设计、机制文档；保留当前入口，旧稿按版本归档 |
| `research/` | 49 | 23.10 MiB | 49 | 方法论文与阅读记录；研究资料，不进入部署包 |
| `competition/` | 42 | 18.84 MiB | 42 | 竞赛交付与参考稿；可独立归档，不进入部署包 |
| `TODO/` | 2 | 18.34 KiB | 2 | 两项待办；可并入design对应计划 |
| `artifacts/` | 130,997 | 1.94 GiB | 0 | 执行历史、原始证据、导出包；按可恢复性和保留策略整理 |
| `.local-workspace/` | 34,118 | 1.86 GiB | 0 | 比较项目副本、缓存和渲染工作区；优先检查可再生成部分 |
| `.venv/` | 14,880 | 325.45 MiB | 0 | 根目录Python环境；统一解释器入口后再考虑撤销 |
| `.git/` | 4,470 | 194.10 MiB | 0 | 版本历史与对象；保留，由Git管理 |

根目录另外保留`README.md`、`AGENTS.md`、`LICENSE`、Git/CI配置和本地`.env`。索引没有读取或输出配置凭据内容。

```text
semflow-audit/
├── system/                         系统代码和工程工具
│   ├── backend/app/                API、适配器、服务、契约、工作流、存储、Prompt
│   ├── frontend/src/               前端源码
│   ├── scripts/                    初始化、工具安装、归档与评测runner
│   │   └── benchmarks/             当前177个直接文件，适合按评测项目分组
│   ├── tests/                      回归测试与合成夹具
│   ├── agents/openhands/            可选OpenHands引擎与独立锁文件/环境
│   ├── knowledge/                  生产知识种子
│   └── runners/                    隔离验证镜像
├── benchmarks/                     评测资产与结论
│   ├── datasets/                   版本化公开数据包
│   ├── experiments/                协议、配置、状态及历史轮次
│   ├── reports/                    结果、诊断与消融报告
│   ├── testing/                    测试说明、冻结记录与渲染稿
│   ├── papers/、catalog/、manifests/ 论文、来源和校验索引
│   └── raw/、model-inputs/、evaluator-only/  本地展开数据，已忽略
├── design/                         设计和模块边界，含本次机制文档
├── research/                       方法论文与笔记
├── competition/                    竞赛交付；适合独立归档/交付
├── TODO/                           尚未并入设计入口的待办
├── artifacts/                      执行历史和研究证据，已忽略
├── .local-workspace/               比较项目副本与临时工作区，已忽略
└── .venv/                          根环境；另有system和OpenHands环境
```

## 3. 重点子目录

| 路径 | 文件记录 | 逻辑体积 | 判断 |
| --- | ---: | ---: | --- |
| `system/backend/app/` | 517 | 2.93 MiB | API、适配器、契约、服务、工作流、持久化与Prompt；包括本地字节码缓存 |
| `system/frontend/src/` | 138 | 414.88 KiB | 前端源码 |
| `system/frontend/node_modules/` | 15,577 | 359.07 MiB | 前端依赖，可用锁文件重装 |
| `system/.venv/` | 14,728 | 323.12 MiB | 当前uv工作区Python环境；本轮测试使用它 |
| `system/agents/openhands/.venv/` | 17,509 | 322.41 MiB | OpenHands独立环境；可选引擎依赖隔离 |
| `system/scripts/benchmarks/` | 318 | 2.33 MiB | 评测runner；177个直接文件，建议按项目分包 |
| `system/tests/` | 222 | 2.42 MiB | 系统与机制回归测试，保留 |
| `benchmarks/datasets/` | 40 | 120.87 MiB | 40个文件，含可发布数据包和入口 |
| `benchmarks/raw/` | 10,878 | 255.53 MiB | 展开的上游材料；需校验恢复能力后才可清理 |
| `benchmarks/model-inputs/` | 6,395 | 16.33 MiB | 模型允许输入；保留与标签的隔离 |
| `benchmarks/evaluator-only/` | 36 | 1.59 MiB | 评测器标签与答案；不得混入模型输入 |
| `benchmarks/experiments/` | 151 | 1.08 MiB | 132个直接文件，包含多轮配置与状态 |
| `benchmarks/testing/` | 92 | 29.33 MiB | 方案、冻结版本和Word/HTML说明 |
| `design/audit-mechanisms/` | 4 | 37.00 KiB | 本次三部分机制分析 |
| `.local-workspace/work/go-build-cache/` | 3,902 | 668.11 MiB | Go构建缓存，较明确的可再生成项 |
| `.local-workspace/zhejiang-competition-project/.work/` | 628 | 420.10 MiB | 旧竞赛渲染、字体及临时构建；交付和字体来源确认后归档 |
| `.local-workspace/realvuln-upstream/` | 10,442 | 426.35 MiB | RealVuln上游副本；与冻结数据核对前保留 |
| `artifacts/runs/` | 56,060 | 470.47 MiB | 审计运行、源码与执行证据；不能按目录名当缓存清空 |
| `artifacts/research/realvuln/` | 2,942 | 205.52 MiB | 本次RealVuln归档与证据 |
| `artifacts/exports/` | 1,066 | 64.98 MiB | 完整交付包和六例取证补充 |

三个Python环境合计 **970.98 MiB**；前端依赖 **359.07 MiB**。环境边界有合理用途，不能仅因为都叫`.venv`就认为逐字节重复。

## 4. 可优先考虑剔除的可再生成项

| 优先级 | 路径/类别 | 逻辑体积 | 处理依据 |
| --- | --- | ---: | --- |
| P0 | `.local-workspace/work/go-build-cache/` | 668.11 MiB | Go编译缓存；不用它执行比较工具时可清理，之后重新编译 |
| P0 | `__pycache__/`、`.pytest_cache/`、`.ruff_cache/`等工具缓存 | 4.68 MiB | 可再生成，清理不改变源码或原始测试证据 |
| P0 | 根目录/其他位置的`.DS_Store`和独立日志 | 24.31 KiB | 体积很小；先保留仍在排查的问题日志 |
| P1 | 前端构建副本 | 759.85 KiB | 可重新构建；正在用作静态服务时保留 |
| P1 | `system/frontend/node_modules/` | 359.07 MiB | 有锁文件，可重装；清理后前端开发/构建需恢复依赖 |

前四类互不重叠，逻辑体积约 **673.56 MiB**；再计Node依赖约 **1.01 GiB**。这是候选规模，不是承诺的可释放物理空间，也不意味着已确认相关进程停止。

## 5. 需要先归档或调整入口的内容

**根`.venv/`**：325.45 MiB，与`system/.venv/`并存。本项目常规uv工作区和本次测试使用`system/.venv`；`start_ui_local.ps1`和`prepare_ui_local.py`为独立`semflow-audit-ui`工作区保留根环境约定。因此可先明确主项目/独立UI的启动入口，再决定根环境是否退出，不直接把它标为无用。

**旧竞赛`.work/`**：420.10 MiB，主要是渲染和字体构建材料。确认`competition/deliverables/`最终作品和必要字体来源有独立可恢复副本后，可以归档临时构建目录。

**`.local-workspace/realvuln-*`**：保留上游与历史原件的区别。当前DVGA完整冻结源码尚未找齐，不能为了缩小目录把这些来源副本一并清掉；先按已有快照/证据哈希核对。

**`artifacts/`**：包含真实运行、模型响应、Evidence、冻结实现和导出包。适合采用“不可变归档＋成员SHA＋恢复入口＋保留策略”，验证恢复后清理可再生成展开副本。单个大文件或重复路径不是删除依据，已有便携包清单还可能引用这些路径。

**`benchmarks/raw/`等展开输入**：273.45 MiB。已有[数据包恢复工具](../system/scripts/benchmarks/archive_research_materials.py)，应先校验特定数据确实在归档内，再处理展开副本。真实模型允许输入和评测答案继续分开。

## 6. 真正能简化阅读与维护的结构调整

1. **评测脚本按项目分包**：`system/scripts/benchmarks/`当前177个直接文件，其中40个含Vul4Py命名、11个含OpenHands命名（命名集合可能重叠）。可整理为`realvuln/`、`vul4py/`、`discovery/`、`rules/`和`common/`。迁移时保留旧CLI入口或映射，更新导入与测试。
2. **实验协议按系列归档**：`benchmarks/experiments/`132个直接文件，其中55个Vul4Py命名。当前协议与`state`留在入口，历史`resumeN`、environment/runtime版本放到系列/日期目录；历史收据的路径和哈希仍可解析。
3. **一个当前设计入口**：`TODO/multi-language-audit.md`与对应设计计划互相链接，统一待办状态；`design/development/`和旧流程图标注历史版本。它们可能内容重叠，尚未证明可以直接删除。
4. **研究/竞赛不进入部署包**：保留研究仓库中的可追溯来源，发布时使用允许清单。`competition/`和`research/`本身体积不大，迁走主要改善职责边界，而非解决GiB级占用。
5. **后端按领域导航**：当前`services/`73个直接文件，建议先补领域导航（发现/复审/修复/规则/知识），再按依赖边界考虑包结构。保持证据、门控、调度的职责，避免为了文件数少而合成大文件。

这些都是待审阅方案，本轮没有执行重命名、合并文档或迁移代码。

## 7. 精简部署包的建议边界

运行交付保留`system/backend/`必要源码/迁移/入口、`system/pyproject.toml`与`uv.lock`、`system/compose.yml`、知识种子、验证镜像定义、构建后的前端、`system/.env.example`及基本说明/许可。OpenHands启用时另带独立依赖定义与运行环境准备方式。

构建阶段使用前端源码与锁文件；运行交付排除`node_modules`、本地虚拟环境、测试历史、论文、竞赛稿和工作副本。源码目录层级及配置查找规则保持匹配，不能简单搬平backend导致路径解析失效。

原始审计数据通过独立持久卷/归档管理；部署包大小与研究工作区大小分别衡量。这样可以让同学继续实验，同时让服务端交付保持较小。

## 8. 重复文件检查和索引边界

本轮对**Git跟踪、至少64 KiB、大小相同**的候选计算SHA-256，发现 **0组完全相同的大文件**。这不覆盖小文件、Git忽略数据、近似内容或同一文档的不同渲染格式；不据此声称工作区完全没有重复。

扫描未跟随符号链接，0个读取元数据错误。忽略状态按Git跟踪/可见未跟踪清单推断；嵌套副本随父目录归类。活动进程、资料是否只有一份、数据能否恢复，都不能由体积推断。

原始元数据：[inventory.json](../artifacts/research/verification/20261102-project-index/inventory.json)、[目录CSV](../artifacts/research/verification/20261102-project-index/directories.csv)。扫描时间点之后的提交和新产物会改变数量；快照用于本次审阅。

复现命令（只读文件元数据，只对上述重复候选读内容，不读`.env`凭据、不执行第三方项目）：

```sh
python3 system/scripts/project_directory_index.py --output artifacts/research/verification/20261102-project-index
```

**下一步可先整理范围最明确的缓存；目录重组和证据归档分别实施、分别验证。本轮仅提交索引与建议，没有删除任何文件。**
