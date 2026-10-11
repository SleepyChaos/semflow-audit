# 仓库目录与材料归档

整理日期：2026-10-11。按实现、设计、实验和原始材料划分职责；已有源码与实验脚本的位置保持兼容，历史报告和执行收据保持原样。

```text
semflow-audit/
├── backend/                     # FastAPI、领域用例、LangGraph、适配器和数据库迁移
│   └── app/
│       ├── api/                 # 路由与所有权检查
│       ├── contracts/, domain/  # 输入输出契约与状态约束
│       ├── services/            # 发现、复核、修复、规则生成用例
│       ├── workflows/, jobs/    # 图节点、任务调度与执行入口
│       ├── adapters/, ports/    # CodeQL、LLM、检索、证据与隔离验证
│       ├── persistence/         # 持久化记录与仓储
│       └── prompts/             # 独立版本化 Prompt
├── frontend/                    # 工作台、业务面板与前端验证
├── runners/                     # 隔离验证镜像
├── tests/                       # 审计行为、任务隔离、证据和失败测试
├── scripts/                     # 初始化、知识采集、实验与归档工具
├── docs/                        # 设计、研究记录、测试方案与结果索引
│   ├── research/                # 文献分析、实验协议、历史结果与设计提案
│   ├── testing/                 # 当前测试方案、Word/HTML、不可变版本索引
│   └── knowledge/               # 生产知识材料说明
└── benchmark-data/
    ├── catalog/                 # 三方向来源、固定版本、用途与许可登记
    ├── papers/                  # 已收集论文、方法/竞品材料与阅读包
    ├── datasets/                # 可推送的测试数据压缩包
    ├── dataset-notes/           # 作者 README 与完整测试范围说明
    ├── references/              # 已提供的竞品说明文档
    ├── test-programs/           # 功能分类、对照协议与材料盘点
    ├── experiments/             # 实验脚本、历史报告、状态与日志
    └── manifests/               # 来源、SHA-256、归档成员与排除记录
```

## 查找与恢复

| 要找的内容 | 入口 |
| --- | --- |
| 启动与实现边界 | [README](../README.md)、[模块边界](architecture.md) |
| 设计、计划与阶段记录 | [文档导航](README.md)、[研究导航](research/README.md) |
| 论文、测试论文与竞品全文 | [论文库](../benchmark-data/papers/README.md) |
| 公开测试数据与固定源码 | [数据归档](../benchmark-data/datasets/README.md) |
| 测试集范围和作者说明 | [测试集说明](../benchmark-data/dataset-notes/README.md) |
| 当前测试方案、Word 和结果版本 | [测试归档](testing/README.md) |
| 实验状态和断点续接 | [实验入口](../benchmark-data/experiments/README.md) |
| 可运行的维护/实验命令 | [脚本导航](../scripts/README.md) |

测试数据压缩包恢复到原有 `benchmark-data/raw/`、`evaluator-only/`、`model-inputs/` 路径。解包副本继续忽略，避免数万份第三方文件挤占源码目录；远程仓库保存压缩包和逐成员校验清单。

```sh
python3 scripts/benchmarks/archive_research_materials.py
python3 scripts/benchmarks/archive_research_materials.py --restore
```

第一条只验证，第二条验证后恢复缺失文件；已有文件内容不一致时拒绝覆盖。数据含答案、修复版本和作者输出，仍按实验协议隔离评测器与模型输入。

`.env`、运行依赖、真实上传、审计产物、CodeQL 数据库及 `.local-workspace/` 继续仅本地保存。公开样本中嵌入的测试凭据已在发布副本中移除，压缩包中无法直接发布的传输文件、失败下载和扫描产物逐项列入排除清单；本地原件未改动。过滤后副本不应冒充完整原始实验环境。

材料沿用各自上游许可，来源和固定提交见 `catalog/` 及归档清单；本次整理不证明全部基准已经执行或通过。
