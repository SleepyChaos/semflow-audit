# Semflow Audit UI V2 本地启动

新版代码：D:\semflow-audit-ui。原版 D:\semflow-audit 独立保留。

在 VS Code 打开新版目录，PowerShell 终端运行：

```powershell
cd D:\semflow-audit-ui
.\start-local.cmd
```

浏览器访问 http://127.0.0.1:5174，新 API 在 http://127.0.0.1:8001。
停止新版运行 `.\stop-local.cmd`；它只操作新版进程和 semflow-audit-ui 容器，保留新版数据。

## 隔离与数据

数据库与 Redis 使用单独的容器和卷，默认主机端口 15440/16380，实际选择保存于本地 .env。初始库没有原版审计任务；上传测试包后建立自己的记录。
测试包在 artifacts/test-uploads，项目源码可上传 ZIP（最多20MB）。
Python 虚拟环境、前端依赖、CodeQL工具/查询包、审计产物均在新版目录。脚本通过只读的现有 Python 安装创建独立虚拟环境；不能把旧 .venv 直接复制来用。
模型配置随本地 .env 私密保留，前端不会显示密钥。不要提交 .env、上传项目或运行产物。

## 检查

日志：artifacts/local/{api,worker,frontend}.{out,err}.log。
启动失败先检查 Docker Desktop 和本目录日志，原版仍可在 5173 使用。
RAG 所需官方知识使用 scripts/seed_ui_xss_knowledge.py 导入（准备好后可运行）；规则发布仍需真实编译、样本/独立测试、项目回扫和人工验收。
新版界面、代码位置、演示顺序与实际 RAG 限制见 docs/UI_WORKBENCH_DELIVERY.md。
官方资料初始化（只在独立副本运行）：
  .\.venv\Scripts\python.exe scripts/seed_ui_xss_knowledge.py
此脚本保留固定来源 SHA 与 compiler-only 检查，不代替独立规则验收。
