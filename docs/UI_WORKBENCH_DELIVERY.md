# 独立工作台 V2：运行与演示说明

目录：`D:\semflow-audit-ui`，分支：`codex/workbench-redesign`。
原版 `D:\semflow-audit` 保持原样。

## 启动与停止

在 VS Code 打开新目录，在 PowerShell 终端执行：

```powershell
cd D:\semflow-audit-ui
.\start-local.cmd
```

访问 http://127.0.0.1:5174 。API 使用 8001，数据库 15440，Redis 16380。
先启动 Docker Desktop；脚本只管理新副本的 API、worker、Vite 和显式 Compose 项目。
停止新版使用 `.\stop-local.cmd`，数据卷会保留。

## 页面和实现位置

- 总览：`frontend/src/features/overview/Overview.tsx`，真实任务与待办统计。
- 任务：`frontend/src/features/audit-task`，列表、上传、详情、身份去重与下一步建议。
- 左侧四阶段：`frontend/src/features/shell` 和 `routes/_layout/audits.$auditId.tsx`。
- AI 复审：`features/ai-review`，候选/证据工作区，记录人工判断。
- 修复与报告：`features/repair`，报告独立导出、确认缺陷选择及隔离验证。
- RAG / 规则库：`features/rules`，生成条件、缺失材料、真实验收和发布操作。
- 知识库：`features/knowledge`，资料列表、来源、CodeQL 库版本、分块与索引状态。
- 视觉样式：`frontend/src/styles`，按公共壳层和各页拆分。
- 原后端业务接口及人工验收边界保留。

## 建议录屏顺序

1. 总览：讲清静态告警、AI 候选、人工确认是三个不同数字。
2. 审计任务：打开“Flask GET 路由 · XSS 演示”，在左侧自由切换四阶段。
3. CodeQL 审计：该实际示例基线静态告警 0；零告警不能解释为没有漏洞。
4. AI 复审：展示 AI 候选、app.py 源码、证据选择和人工判断历史。
5. 修复与报告：报告可在修复前导出；补丁仅针对已人工确认缺陷。
6. RAG：分别介绍目标、检索策略、独立测试、样本批准、项目根因确认和发布。
7. 知识库：展示已导入官方资料的语言库版本，BM25 无需先建向量索引。

演示 ZIP：`artifacts/test-uploads/flask-xss-route-example/flask-get-xss-vulnerable.zip`。
源码快照前缀 `75127fd2a52abf99`，对应此前用户明确确认的同一个未转义返回示例。
新库中的人工判断依据已注明用户对该同一源码的确认，未自动批准新生成样本。

## 真实验证结果与限制

2026-10-11，在新库、新队列与新产物目录执行：

- 新任务真实上传、双引擎扫描完成：静态告警 0、AI 候选 1。
- 统一复核完成；同一源码人工确认已记录。
- Markdown 报告通过网页实际下载。
- 新知识库导入 22 份固定官方 API 参考和 2 个官方 XSS 查询范例；
  范例通过真实 compiler-only 检查，未声称通过独立测试。
- 无测试网络拦截打开全部页面，浏览器未出现 pageerror。
- 1920×1080、1366×768 与 375px 布局验收；桌面复审主按钮及源码在首屏可见。
- RAG 实际提交可执行，但本次新库生成尚未通过后端开发样例验证，暂无可发布规则。
  失败、日志及不可变重跑记录均保留；未修改验收规则或伪造成功。
- 中文描述在当前 BM25 固定检索槽中可能缺少 API 词汇，产生材料未命中。
  已验证包含 `ReflectedXssQuery ReflectedXSSCustomizations ApiGraphs DataFlow TaintTracking`
  的 XSS 描述可实际命中五个检索槽，但模型输出仍须通过编译和样例执行。
- 不复制旧库已发布规则与人工验收状态。规则库空状态属于真实新库状态。

界面截图保存在 `artifacts/local/ui-preview`：
overview.png、tasks.png、scan.png、review.png、repair.png、rag.png、rules.png、knowledge.png。

## 检查命令

```powershell
cd D:\semflow-audit-ui\frontend
$env:SWC_NATIVE_BINDING_CACHE = Join-Path $env:USERPROFILE '.semflow-swc-cache'
D:/node.exe D:/node_modules/npm/bin/npm-cli.js run build
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:5174'
$env:PLAYWRIGHT_CHANNEL = 'chrome'
D:/node.exe ./node_modules/@playwright/test/cli.js test --workers=1
```

Biome 应在 frontend 目录对修改文件运行 check，不运行全仓 unsafe 自动改写。
后端相关回归（项目根目录）：

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m pytest tests/test_ui_isolation.py tests/test_codeql_windows.py tests/test_audit_core.py tests/test_material_integrity.py -q
```

## 实施决策

- 采用完整复制而非链接 worktree，满足用户要求；代价为额外磁盘和依赖安装。
- Windows 无 Bash，改用 PowerShell 保留任务账本和红绿测试证据；代价为不直接运行技能的 Bash 包装脚本。
- uv 缓存和临时目录统一使用 D 盘，解决跨盘文件持久化错误；代价为 D 盘增加缓存。
- 保留独立本地分支，按用户要求不合并、不推送；后续共享版本需另行指定。

检查结果：前端 Playwright 25/25、后端相关回归 26/26，TypeScript/Vite 构建和本次修改文件 Biome 检查通过。
原版 573 个源码文件哈希无变化；原版 5173/8000 与新版 5174/8001 均 HTTP 200。
