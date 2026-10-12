# 多页面审计工作台 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在独立副本中实现适合视频演示、可真实操作的 V2 多页面审计平台。

**Architecture:** 保留现有后端接口，扩展 TanStack 文件路由和公共导航，抽离任务摘要与状态派生逻辑，重整四阶段组件。新副本有自己的服务端口、数据库、队列、产物与进程控制；四阶段作为当前任务的左侧自由切换菜单。

**Tech Stack:** React 19、TypeScript 6、Vite 8、TanStack Router/Query、Tailwind 4、现有 shadcn/Radix 与 lucide、Playwright；现有 FastAPI/Celery/PostgreSQL/Redis/CodeQL。

**Spec:** D:/semflow-audit-ui/docs/superpowers/specs/2026-10-11-multipage-audit-workbench-design.md

## Global Constraints

- 全部写入及 Git 提交只在 D:/semflow-audit-ui；分支 codex/workbench-redesign。
- 原目录 D:/semflow-audit 仅作为读取源码、工具和测试包的参考；禁止修改其配置、源文件、数据库或进程。
- V2：侧栏 #F4F3F0、主体 #FCFCFB、炭黑主按钮、强调色 #D66A38、细灰分隔线、小圆角、平面布局。
- 左侧四阶段 CodeQL 审计、AI 复审、修复与报告、RAG 规则自由切换，不使用横向步骤条或强制顺序向导。
- 新前端端口 5174，API 8001，Compose 项目 semflow-audit-ui；数据库端口优先 15440、Redis 16380，绑定冲突只调整新副本配置。
- 新数据库、Redis、artifacts、规则包缓存与进程状态均独立；Python 虚拟环境重新创建。
- 不添加产品依赖；按现有 lockfile 安装。新测试使用已有 Playwright，测试假数据仅存在于测试拦截中，生产 UI 使用真实接口。
- 不提交 .env、密钥、上传项目、运行产物；不打印模型密钥或数据库 URL。
- 未知、加载与请求失败分别呈现，不伪装成零结果或安全；人工判断、样本批准、根因确认、发布沿用服务端约束。
- 手写文件通常 150–300 行，超过 400 行检查职责；生成路由树由插件产生。
- 全局中文文案，保留必要工程术语并解释；独立显示静态告警、AI 候选、人工确认。

## Review Focus

- 浏览器直接打开任务 URL、刷新及前进/后退：保留同一 auditId 和四阶段选择；无账号跳转。归属任务 2。
- 候选请求失败或只加载部分任务：未知不能计为零，原任务表仍可用。归属任务 3。
- 同一候选身份重复，或静态零告警但 AI 有候选：优先保留既有人工作出决定，计数正确、证据不丢。归属任务 4。
- 从欢迎页带入旧深色主题、1366×768 窄桌面和很长项目名：主体保持 V2 可读布局，下拉菜单和主按钮无溢出。归属任务 2、7。
- 新版启动/停止与缺失材料/独立测试集：不能影响原版，不能靠 UI 绕过规则发布条件。归属任务 1、6。每项检查在所属任务中给出具体验证。

## 文件与职责

- scripts/prepare_ui_local.py：新副本运行配置初始化、端口选择和路径约束；不改后端业务逻辑。
- scripts/start_ui_local.ps1、scripts/stop_ui_local.ps1：只管理新副本服务，记录并验证进程与根目录；根目录 cmd 为简短入口。
- scripts/seed_ui_xss_knowledge.py：适配已有官方资料导入流程，以脚本相对路径定位新副本，记录真实来源与编译验证。
- frontend/src/routes/_layout.tsx、features/shell/*：公共壳层、左侧上下文导航、顶栏、环境面板。
- frontend/src/routes/_layout/{index,audits.index,audits.new,audits.$auditId,rules,knowledge}.tsx：薄路由，管理 URL 参数。
- features/audit-task/task-summary.ts、useAuditData.ts、useRunSummaries.ts：身份计数、状态与下一步说明、缓存及限并发请求。
- features/overview/Overview.tsx：总览；features/audit-task/{AuditListPage,AuditDetailPage,NewAuditPage}.tsx：任务页面。
- features/ai-review/{ReviewPanel,CandidateCard,ReviewControls,CandidateWorkspace}.tsx：复核操作、候选与证据双栏。
- features/repair/*、features/rules/*：保留现有真实动作，改为清晰分组、验收摘要与缺失条件提示。
- features/knowledge/{KnowledgePage,KnowledgePanel}.tsx：可见知识列表、分类和导入面板。
- frontend/src/index.css、workbench.css：V2 主题与壳层；需要时按页面拆出样式，避免巨型选择器文件。
- frontend/tests/{workbench,navigation,task-summary,review-workspace,repair-workspace,rule-workspace,knowledge-workspace,layout}.spec.ts：相应行为验收；测试 fixture 独立于生产源码。

## Task 1：独立可运行环境

**Files:** 创建上述 prepare/start/stop 脚本；修改新副本 compose.yml、.env.example、start-local.cmd、stop-local.cmd、frontend/vite.config.ts、frontend/playwright.config.ts、LOCAL_SETUP.md；仅本地修改新 .env。

**Interfaces:** `prepare_ui_local.py` 从 ROOT=Path(__file__).resolve().parents[1] 生成独立配置；start 脚本返回可访问的 5174/8001 服务并把 PID 保存到新 artifacts/local/processes.json；stop 只停止这些进程与 semflow-audit-ui Compose 项目。

- [ ] 检查原版 5173/8000 健康与新端口可绑定性；记录原版源码哈希和服务基线到新副本 artifacts/local，仅输出非敏感结果。
- [ ] 新建 .venv，按 uv.lock 安装后端。使用已有 Python 3.14 解释器 D:/semflow-audit/.tools/python/cpython-3.14-windows-x86_64-none/python.exe 作为只读基础；定位原版 .tools/uv-package 中的 uv 可执行文件。前端执行 `D:/node.exe D:/node_modules/npm/bin/npm-cli.js ci`，只在新 frontend 安装。
- [ ] 初始化新配置，保留模型密钥，设置新 DATABASE_URL、REDIS_URL、FRONTEND_HOST、ARTIFACT_ROOT、CODEQL_PACK_PATH。检查旧绝对路径全部替换；不得运行仍硬编码原目录的 .local-workspace/install-xss-rag.py。
- [ ] 将 CodeQL 二进制及固定查询依赖准备到新副本 .tools/codeql、artifacts/packs，避免默认命令把包、缓存或数据库写回原目录；无需重新拉取已固定的源码版本。
- [ ] 新 Compose 具有显式项目名，启动脚本先等待 db/redis，再迁移并初始化新库，启动新 API、worker 与 Vite；代理改为 8001。旧的 .local-workspace 启动脚本不再作为入口。
- [ ] 验证两个版本均健康，新库初始任务列表为空且数据地址不同；停止并重启新版，原版始终可访问，数据卷不删除。提交仅本任务的代码与文档文件。

## Task 2：V2 壳层与真实多页面导航

**Files:** 创建 features/shell/{AppSidebar,PageHeader,EnvironmentDrawer}.tsx 及各薄路由；修改 _layout.tsx、index.css、workbench.css、components/theme-provider.tsx（仅在需要时）、playwright.config.ts；创建 navigation.spec.ts。

**Interfaces:** `AuditStage = 'scan' | 'review' | 'repair' | 'rules'`；URL stage 校验默认 scan。侧栏仅在任务 URL 中展示四个当前审计菜单；所有菜单以同一 auditId 导航。`PageHeader({title,description,actions})` 与 `EnvironmentDrawer({open,onOpenChange})` 为各页面复用。

- [ ] 写导航测试：打开 `/audits/task-1?stage=review`，AI 复审菜单 `aria-current=page`；点 RAG 规则后 URL 同一 task-1 且 stage=rules；刷新和后退恢复。先运行 `playwright test tests/navigation.spec.ts` 观察失败。
- [ ] 实现四个全局菜单与任务上下文菜单、面包屑、新建审计入口；移除工作台横向阶段条和任务详情重复横向标签入口。
- [ ] 应用 V2 公共主题；主按钮炭黑，橙色用于选中和提示。工作台采用明确浅色主题，欢迎页已有主题功能继续可用，不让旧主题状态污染主界面或 Radix 弹层。
- [ ] 无效 auditId 显示“未找到审计任务”与返回列表；数据请求失败显示读取失败与重试，不伪装为不存在。暂时未完成的页面也具有明确标题和可用导航。
- [ ] 测试加入空库进入、错误参数回退、超长项目名以及欢迎页主题后进入工作台；运行该测试通过、构建通过，提交本任务文件。

## Task 3：任务摘要、总览、列表与上传

**Files:** 创建 task-summary.ts、useAuditData.ts、useRunSummaries.ts、Overview.tsx、AuditListPage.tsx、NewAuditPage.tsx、task-summary.spec.ts；修改 RunList.tsx、UploadForm.tsx 和工作台入口引用。

**Interfaces:** `summarizeCandidates(candidates: Candidate[]): {aiCandidates:number; confirmed:number; pending:number}` 按现有身份规则去重；`getTaskAction(run:AuditRun, candidates:Candidate[]|undefined, stages:StageRun[]|undefined, rules:RuleVersion[]|undefined): {label:string; stage:AuditStage; reason:string}|null`。`useAuditData(auditId:string)` 复用真实任务/候选/阶段/能力查询。`useRunSummaries(runs:AuditRun[])` 返回带加载或错误状态的逐任务摘要；候选读取限制同时四个，复用 candidates 查询缓存。

- [ ] 写浏览器测试：任务 findings=[]、候选一个 AI pending，列表显示静态告警 0、AI 候选 1、人工确认 0；候选接口 500 时显示“无法读取”，不显示候选 0；先运行失败。
- [ ] 实现去重与推荐动作；全部候选请求成功后才展示聚合总数，否则显示统计中/无法统计。扫描状态写为“扫描完成”，不等于安全或审计全流程完成。
- [ ] 总览显示真实任务/活动任务/待确认候选/已发布规则及最近任务继续入口；列表实现搜索、语言和状态过滤，访问所有任务；不给不存在的数据绘制图表。
- [ ] 单独上传页保留 ZIP 20MB、语言、名称和最多四个发布版本选择；上传成功导航到真实返回的 ID；失败保留输入。从规则库可携带 published ruleId，但必须按语言及发布状态校验。
- [ ] 扩充测试确认重复 identity_key 已确认+pending 只计一次且保留人工状态；验证筛选、上传参数与返回 ID、空状态和总计失败。运行测试与构建通过，提交本任务文件。

## Task 4：任务详情与 AI 证据工作区

**Files:** 创建 AuditDetailPage.tsx、ReviewControls.tsx、CandidateWorkspace.tsx；修改 RunDetails.tsx、ReviewPanel.tsx、CandidateCard.tsx、DiscoveryCoverage.tsx、StageHistory.tsx；创建 review-workspace.spec.ts。

**Interfaces:** `CandidateWorkspace({candidates,evidence,stages,busy})` 左栏选择候选，右栏 `CandidateCard({candidate,evidence,busy})` 展示关联证据与判断；切换候选以 candidate.id 挂载，避免理由或证据选择混入另一候选。模型原字段与复核历史建议单独展示，不能擅改 unknown。

- [ ] 写测试：静态零告警仍能查看候选和 app.py 证据；未输入十字符理由或未选择源码/查询证据时确认不可执行，附近说明缺少条件。请求失败不隐藏在历史折叠项中。先运行失败。
- [ ] 任务详情展示项目、快照与摘要，四阶段内容根据 URL 切换；保留取消、恢复、重试、SARIF 下载能力和真实错误。下一步是建议，菜单始终可查看。
- [ ] AI 页面采用 V2 候选/源码双栏，启动复核在第一屏；取证范围、模型步数和独立粗筛作为可见配置组或高级项，人工证据补充可达。
- [ ] 证据与 checkbox 同行、已选明显，源码可读；人工动作支持 confirmed/excluded/pending/insufficient，理由和 evidence_ids 与原接口一致；判断历史按需读取，证据内容和快照摘要保留。
- [ ] 测试断言候选切换清理表单、真实 POST 包含所选 evidence_ids 和 status/reason、人工提交失败保留输入；历史模型建议 supported 与 candidate.model_assessment unknown 分开显示。通过后提交本任务。

## Task 5：修复与报告入口

**Files:** 修改 RepairPanel.tsx、RepairCard.tsx，必要时创建 RepairControls.tsx；创建 frontend/tests/repair-workspace.spec.ts。

**Interfaces:** 沿用 `startStage(auditId,'repair',body)`、`downloadReport(auditId)`、`downloadReportJson(auditId)`、`downloadDiff(repairId)`、`acceptRepair(repairId,reason)`，保留现有 body 字段与隔离验证选择。

- [ ] 测试报告在没有修复记录时仍可导出；仅有 pending 候选时显示“先确认缺陷”及直达 AI 复审；不生成 repair 请求。先运行失败。
- [ ] 将报告动作与修复操作分组；已确认候选 checkbox 与标题同一行，显示选中数量；源码范围、验证方案、CodeQL 复扫有明确标签与说明。
- [ ] 修复生成按钮显示具体禁用原因；Diff、隔离验证、复扫与人工接受状态单独呈现，不能把任务执行完成写成已修复。
- [ ] 验证导出 URL/文件名、修复 POST 保留候选 ID 和高级选项、接受失败保留理由。测试与构建通过，提交本任务。

## Task 6：规则库与 RAG 生成/验收

**Files:** 创建 RulesPage.tsx、RuleGenerationForm.tsx、RuleValidationSummary.tsx；修改 RulePanel.tsx、RuleCard.tsx、ProjectReplayReview.tsx；创建 rule-workspace.spec.ts。

**Interfaces:** RulesPage 使用 `getRules(language?,published=false)`；RuleGenerationForm 消费真实 run、capabilities、confirmed candidates、holdouts；不改变 startStage(auditId,'rule',body) 参数。RuleValidationSummary 只解释实际 validation 字段，缺失项显示未知/待运行。

- [ ] 测试缺模型、目标不足十字、缺源码时生成禁用且显示原因；`materials_missing` 显示缺少参考材料及前往知识库，原错误可展开；没有独立集仍可生成但不能被 UI 判为可发布。先运行失败。
- [ ] 规则库按语言/用途/状态筛选，定位 ruleId，提供回到来源任务和使用已发布版本入口；查询及模块下载/展示、检索引用、停用能力保留。
- [ ] 生成分成目标、检索与策略、验收三个组；保留现有默认 review_anchor，用途主动选择；显示匹配语言和 CodeQL 库版本要求，不预先声称材料齐备或自动勾选独立测试集。
- [ ] 规则卡提供编译、开发样本、独立测试、项目回扫、人工样本批准、根因确认、发布等实际验收摘要；发布仍要求后端 validated，人工动作分开，不自动完成。
- [ ] 测试尚未 validated 无发布动作、已发布可用于新审计、样本与根因确认 POST 参数不丢、重跑有新执行记录；通过后提交本任务。

## Task 7：知识库与录屏适配

**Files:** 创建 KnowledgePage.tsx、knowledge-workspace.spec.ts、layout.spec.ts；修改 KnowledgePanel.tsx、各页面样式、Welcome.tsx（仅必要文案/入口）。

**Interfaces:** `KnowledgePanel({language,embeddingReady,embedded?:boolean})` 支持独立页面展开导入；KnowledgePage 提供语言与 corpus 过滤，并保留真实来源、api_version 说明和返回 auditId 的链接。getKnowledge/importKnowledge/indexKnowledge 接口不变。

- [ ] 测试直接进入知识库有可见“导入知识”入口；材料语言/类型过滤有效，输入 URL 不自动抓取，导入 body 包含正文和 provenance；BM25 未向量化仍显示检索方式可用。先运行失败。
- [ ] 实现知识列表、导入侧面板或可见分组表单、分块/索引状态；缺 embeddings 时明确不能建向量索引，但允许保存资料；索引错误直接可见。
- [ ] 调整 1920×1080、1366×768 和 375px 基础布局；菜单可滚动/折叠，长路径折行，主按钮保持可点击。应用 light 与 portal 一致主题，控制标题/正文/代码字号。
- [ ] layout.spec.ts 验证 document.scrollWidth<=innerWidth、主操作在首屏、键盘菜单和证据 checkbox 可用；记录主页面截图至新版 artifacts/local/ui-preview。
- [ ] 更新现有 workbench.spec.ts 的总览标题与无登录断言，保留欢迎页实际支持的行为。上述测试与构建通过，提交本任务。

## Task 8：真实服务验证、回归与交付

**Files:** 创建或更新 LOCAL_SETUP.md、新版演示说明与验证结果；所有运行证据保存在新 artifacts/local，不提交实际审计产物。

**Interfaces:** 新版运行地址 5174/API 8001；实际能力、任务、候选、规则、知识来自新后端，不依赖测试拦截或图片数据。

- [ ] 按新入口启动所有服务，用新 Python 执行适配后的 `scripts/seed_ui_xss_knowledge.py`。将旧 importer 的硬编码原目录和 API 地址改为当前脚本根路径/新配置；导入固定官方 API 资料和规则范例，保留 SHA、许可证、版本与真正 compiler-only 标记，不造完整测试记录。
- [ ] 完成无测试拦截的浏览器验证：总览、上传、扫描结果、AI 复审、报告、RAG 页面、规则库与知识库入口。需要后台结果时在新库上传真实测试 ZIP；模型步骤只运行验证所需最小次数，不能复用旧库人工确认当作新确认。
- [ ] 已有人工确认适用范围必须保留：用户对实际 XSS 根因认可可用于新副本同一源码，但样本/根因必须与新实际结果一致，不批准不同生成样本。遇到新判断要求据实呈现，不为了录屏跳过验收。
- [ ] 执行构建：`$env:SWC_NATIVE_BINDING_CACHE = Join-Path $env:USERPROFILE '.semflow-swc-cache'; D:/node.exe D:/node_modules/npm/bin/npm-cli.js run build`（frontend）；对本次变更文件运行 Biome check，不使用全仓 --write --unsafe。
- [ ] 执行前端检查：`$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:5174'; $env:PLAYWRIGHT_CHANNEL='chrome'; D:/node.exe ./node_modules/@playwright/test/cli.js test`（frontend）。测试允许固定网络 fixture；实际服务验收需另记录未拦截页面结果。
- [ ] 有后端脚本或环境变更时运行相关现有回归：`$env:PYTHONPATH='backend'; ./.venv/Scripts/python.exe -m pytest tests/test_codeql_windows.py tests/test_audit_core.py tests/test_material_integrity.py -q`。不因界面改变重跑全部成本较高的模型/CodeQL 验收。
- [ ] 核对原版源码基线、5173/8000 服务及容器无修改；新版进程/端口、数据库、Redis 与 artifacts 路径相互独立。整分支差异审阅，修正发现后重复受影响检查。
- [ ] 最终展示新版地址、启动/停止命令、独立目录、四页面截图、真实验证结果及未完成项；提交交付文档，保证 .env 与运行产物未入 Git。

## 执行方式待选择

建议 Native：在当前会话由主代理逐项实施，阶段验证通过后继续，最后做独立整分支审查。这些页面共享路由和任务状态接口，按顺序改造便于及时检查一致性。

另一方式 Subagent-driven：每个任务使用新子代理实现并逐项独立审阅，适合强调多次独立检查的情况。

本计划只完成规划，待用户审阅计划并选择执行方式后开始产品实现。