# 解耦代码复核：操作验收前

DEC-REV-000 | 2026-11-13T11:36:00+08:00 | completed

状态仅表示本次静态审查已完成。未运行测试、构建容器或启动 GUI/CLI 业务。本轮只新增验收文档并链接主 TODO，没有修改实现、AGENTS.md 或真实平台实例。运行验收见[操作清单](backend-decoupling-acceptance-checklist-20261113.md)。

## 结论

**架构方向基本符合用户目标：三套研究功能已进入独立包，当前受支持的 CLI/Web 路径调用同一 research public；平台状态和展示通过桥接处理。现有证据不足以认定“两边完整正常使用”已经最终通过。**

本次发现独立 discovery 安装路径和平台容器构建路径的明确静态缺陷，以及一处规则 CLI 文档/生命周期冲突。应最小修复并实测；不要求推倒现有抽象、不要求清理所有 legacy。S6 是既有边界与文档收口，不能替代实际应用启动和当前发行物业务操作。

## 高优先级发现

### DEC-REV-001 | 2026-11-13T11:36:00+08:00 | planned

**P1：独立安装后的 discovery 命令仍依赖源码仓库布局。**

位置：[discovery_requests.py](../../system/research/src/semflow_research/public/discovery_requests.py)，`assemble_discovery` 第 237～239 行；[discovery_commands.py](../../system/research_cli/src/semflow_cli/discovery_commands.py) 的四个最小入口。

实现通过 `Path(__file__).resolve().parents[4] / "uv.lock"` 读取依赖摘要。源码布局下它指向 system/uv.lock；wheel 安装到 site-packages 后会指向虚拟环境祖先目录，那里没有约定或打包的 uv.lock。research 的 wheel 配置只打包 src/semflow_research。四个 discovery 命令也没有 repair/rules 所提供的显式 `--dependency-lock` 参数。

因此仓库内测试、import/help/schema 全通过，仍无法证明仓库外独立命令能运行；缺少文件时在运行算法前就会抛出 FileNotFoundError。此处是路径推导得到的静态结论，本轮未现场运行复现。

验收要求：在仓库外空环境安装本轮 wheel，执行 discovery-scan 和 discovery-discover 实际命令；明确提供或随包冻结依赖身份。不能用把 uv.lock 塞进任意父目录、源码 PYTHONPATH 或复制 backend 的办法通过。只修资源装配边界，不建设新的发行系统。

### DEC-REV-002 | 2026-11-13T11:36:00+08:00 | planned

**P1（已有容器交付路径）：Dockerfile 没有复制新增 workspace 包。**

位置：[backend/Dockerfile](../../system/backend/Dockerfile) 第 15～19 行；[system/pyproject.toml](../../system/pyproject.toml) workspace；[backend/pyproject.toml](../../system/backend/pyproject.toml) 第 7、38 行。

根 workspace 已包含 backend/contracts/research/research_cli，backend 也新增 workspace 依赖 semflow-research。但 Docker 构建仅复制根配置与 backend 文件，然后执行 `uv sync --frozen --package app --no-dev`。镜像此时没有 contracts、research 或 research_cli 的包定义/源码，无法按当前 workspace/依赖构建。

这是新增依赖与未同步打包流程的断裂；宿主机 .venv 启动成功不能证明 Docker 交付成功。本轮未构建镜像，因此不提供虚构错误日志。最小修复后在副本按 Dockerfile 首行说明构建并保留日志；无需借机容器化整个 CodeQL 运行架构。

### DEC-REV-003 | 2026-11-13T11:36:00+08:00 | planned

**P2：文档示范的规则批准后复核顺序与代码约束不一致。**

位置：[research_cli/README.md](../../system/research_cli/README.md) 第 19～24 行；[rule_validation.py](../../system/research/src/semflow_research/public/rule_validation.py) 第 17～40 行；[test_rule_minimal_cli.py](../../system/research/tests/test_rule_minimal_cli.py) 第 55、74 行。

README 按 rule-generate→decide→resume→rule-validate 展示。`rule_validation.assemble` 却要求被引用的生成执行当前仍有 pending_action，并使用当前 revision 验证待批准命令。resume 完成后不再有 pending_action，因此同一命令文件会触发 approval_required。现有测试在 resume **之前**调用 rule-validate，未覆盖文档顺序。

不预设必须新增“完成后重新验证”功能。应明确本轮交付语义：如果 validate 仅用于批准前独立技术复核，就修正文档和说明，并给出完整可操作顺序；若承诺生成完成后独立复核，则补最小的已批准主体读取路径与必要测试。不能以另一个顺序测试通过来宣称 README 已验证。

## 已有正面证据及限度

| 目标 | 本次检查到的代码证据 | 判断范围 |
| --- | --- | --- |
| core 不依赖平台 | AST 扫描 research 205、contracts 34、CLI 5 个 Python 模块，未见 app/FastAPI/Celery/SQLModel/pydantic_settings 导入 | 静态导入通过，不等于资源路径与运行依赖全部独立；REV-001 是反例 |
| CLI 直接接 core | CLI dispatch→public.runs.execute→discovery/repair/rules；批准恢复也经 public | 没有经过平台 HTTP/ORM；独立安装的实际业务操作待验 |
| Web 使用同一 core | research_bridge runtime/repair_runtime/rule_runtime 调用对应 public；两端导入 research 均限制在 public | 当前绑定执行使用同一科研算法，bridge 仍有装配/投影复杂性，但不是本轮审美问题 |
| 新旧执行区分 | stage_lifecycle 建 ResearchBinding，runtime.stages 对绑定执行拒绝切回 legacy graph | 受支持版本进入新 core；旧版本/历史执行保留旧入口，不能泛称任意版本全迁移 |
| 三个内核算法迁移 | extraction-map 现有 120 项；抽查 repair_semantics/rule_synthesis 与旧归档，ORM/global config 转为显式 _kernel 上下文 | 主要迁移方向正确；并非每个算法分支已做穷尽等价审计 |
| Prompt 复用 | 迁移前归档 44 个 Prompt 文件，在 research 中均找到字节一致副本 | 模板未被悄悄改写；装配后的上下文、默认参数仍需执行对照 |
| 契约与平台投影 | discovery projection 验证 ResultEnvelope/manifest/身份，保留 model_assessment；CLI/bridge 有 WIRE 收发注释 | 契约和语义说明已落地，不要求平台 DTO 字节同构；实际数据往返仍需验收 |
| 既有测试证据 | 读取 JUnit：S5 66 cases/2 skip/0 failure/error；独立 169/3 skip/0 failure/error；S6 23/0 skip/0 failure/error | 对应 64、166、23 passed，未在本轮重跑，不相加冒充唯一用例数 |

静态 AST 只覆盖普通 import/from，不代表穷尽动态加载。手工检查了主要公共入口与绑定分发；结论不是全仓安全审计。

## 迁移前后 diff 的取证口径

- 使用真实迁移前归档 `20261110T152154-ebb9cb83`，549 文件，归档 SHA-256 已核验为 `2241989b58b3889a12a3b221fb141d6b9e3d3ac9af7b5569f72c0facb2dde01e`。
- 对归档逐文件比较：本次读取时 29 个已变更、0 个缺失；大量 research/contracts/bridge 是新增文件，不在这 29 个中。该数字不是整个解耦改动规模。
- 当前工作区含迁移前已存在的修改及未跟踪新增文件，`git diff` 不能独自表示这次迁移。不能把 HEAD 到工作区的所有实验/前端变化归责于解耦。
- 已检查旧→新 `stage_lifecycle`、`runtime/stages`、`services/repair`、`repair_semantics`、规则路由；修复完成后的任务派发由算法服务移至平台 runtime/followup，符合平台拥有编排的目标。
- 已抽查迁移算法：修复和规则生成保留原流程并注入显式 context；candidate_classification 从修改人工 status 改为仅写 model_assessment。后者是实质语义变化，符合“不冒充人工确认”的既定边界，但 before/after 报告必须列出，不能按“纯搬迁零行为变化”描述。
- 旧源 hash 与新 SourceManifest digest 的算法不一致；桥接显式保存 legacy 与科研身份。比较必须验证各自摘要对应相同字节，不能比较两个不同定义的 hex 后报错，也不能简单忽略。

## 待现场核验的风险，不扩为重构要求

1. **完整 CLI 实用性**：native generate 已有最小命令，但 suite/verify 文档仍使用 run --spec。要现场核实完整链路的输入准备成本，不能只证明高级 API 存在。若必须借助平台或手写整套内部协议，才构成用户“极简 CLI”目标的缺口。
2. **真实 GUI**：frontend/tests 大量 page.route/mock，已存“Web/worker”集成证据不等于浏览器+HTTP+Celery 的真实服务运行。下一轮必须实际点击上传、发现、修复/Diff、规则批准/恢复/发布。
3. **真实工具证据范围**：既有 native 样本使用真实 CodeQL/Docker但模型/操作者是替身；OpenHands SDK 样本模型为 scripted；真实规则样本明确未请求 project replay。三者都不是完整现场模型与 GUI 证明。
4. **前后/双端比较**：已有部分 process 测试从 Web 冻结请求拷贝到 CLI run，能证明同一 core 消费同一 spec；不能独自证明两个最小入口分别装配的语义相等。应比较双方实际生成的 spec，并单列迁移前归档基线对照。
5. **配置默认值**：CLI discovery 的 scout_method_version/prompt 默认 8，平台存在版本 7 的默认路径。不同方法结果不同未必是缺陷；验收显式设相同参数，避免错误归因。前端 Vite 5174/API 8001 与旧 README 端口也不同，隔离启动必须显式对齐。这类原有文档问题不全部归责于解耦。

## 最终复核栏（运行后填写）

DEC-REV-004 | 2026-11-13T11:36:00+08:00 | planned

由监督会话读取 ACC 运行报告并审查本次最小修复 diff，填写：验收前/后代码摘要；REV-001/002/003 的复现和关闭证据；独立 CLI 与真实 GUI 的实际结果；同参双端与迁移前后差异；剩余阻断与外部限制；整体是否达到用户目标。

当前最终判定：**代码边界基本达标；操作验收未完成，暂不作无条件整体通过结论。** 不因此新增架构阶段，优先关闭真实使用阻断。
