# 仓库目录与归档规则

2026-10-12 按用途整理为五个主目录：

```text
semflow-audit/
├── system/                 系统源码、配置、锁文件、测试及脚本
│   ├── backend/            API、Worker、适配器、Prompt与数据库迁移
│   ├── frontend/           前端源码与构建配置
│   ├── scripts/            初始化、知识采集、实验与归档工具
│   ├── tests/              系统测试
│   ├── knowledge/          生产知识种子与规则资料
│   └── runners/            隔离验证镜像定义
├── benchmarks/             测试集、基准论文、评测方案及结果
│   ├── datasets/           可发布的数据包
│   ├── papers/             基准与数据集论文
│   ├── testing/            测试方案及版本冻结记录
│   ├── experiments/        正式实验协议与结果
│   └── reports/            专项测试、消融与失败记录
├── research/               代码审计方法与竞品研究
│   ├── papers/             方法、规则、修复及竞品全文
│   ├── notes/              阅读笔记与评估
│   ├── reading/            既有精读材料包
│   └── catalog/            书目、来源和校验清单
├── design/                 架构、设计、开发及验收计划
└── competition/            作品报告、模板、校对及配图
```

根目录保留总 README、AGENTS、LICENSE、Git配置和 CI；每个主目录都有 README 索引。基准论文与方法论文按用途保存一份，完整论文表用链接连接两处。测试脚本属于系统代码，测试输入、协议和实测报告属于 benchmarks。

## 运行路径

开发命令默认从 `system/` 执行，uv工作区环境位于 `system/.venv`。API和Worker仍读取仓库根目录 `.env`，`ARTIFACT_ROOT` 默认仍为仓库根目录 `artifacts/`，既有数据库卷及本地执行历史继续使用。Compose从system目录执行时显式指定 `--env-file ../.env -p semflow-audit`，避免目录名称改变后启动新的卷。

`.env`、本地环境、展开的基准输入、真实上传项目和审计产物由 Git 忽略。竞赛临时渲染缓存保留在 `.local-workspace/`，最终作品和校对材料进入 competition。

## 历史与核验

[repository-file-map.json](repository-file-map.json)记录迁移前800个受版本控制文件的旧路径、新路径与原始SHA-256，另列竞赛资料的导入来源和哈希。历史 `benchmarks/testing/20261009-workspace-*` 冻结记录保留原始字节；其中旧路径引用可通过迁移清单定位，归档工具校验时也会解析映射。

当前可执行路径、README索引与来源清单适配新目录；不以今天的配置改写历史测试成绩。资料适用各自许可，压缩包中的答案、规则与PoC不得直接混入模型输入或生产知识库。
