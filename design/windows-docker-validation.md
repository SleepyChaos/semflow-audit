# Windows Docker 兼容性验证

日期：2026-11-06。验证范围为 Windows 11 + Docker Desktop 的 WSL2/Linux amd64 容器，不表示 Windows 原生容器或全部业务链路已验证。

## 环境与修复

- Windows 11 Pro，build 26100；Docker Desktop 4.79.0、Engine 29.5.3、Compose 5.1.4。
- API/Worker Python 3.14.10，CodeQL 2.23.5，抽取 Python 3.11.14。
- 固定查询包：Python 1.6.0、JavaScript 1.4.0；本次实际扫描 Python。
- Linux Python 工具包包含仅大小写不同的文件名，直接解压或复制到大小写不敏感的 Windows 目录会冲突。Linux 工具改存 Docker 命名卷，API/Worker 只读使用；源码及产物继续绑定 Windows 项目目录。
- 新增可选 `tools` 服务，从官方固定资产下载并校验 SHA-256。工具准备容器不加载模型或数据库凭据。

## 可重复的检查

按根目录 `DOCKER.md` 启动服务、准备工具及模型配置后运行：

```sh
python system/scripts/docker_smoke.py --output artifacts/local/docker-smoke.json
```

该脚本自动生成一份六行 Flask 源码，含预期的注入问题；不运行示例 Web 服务。源码使用 CRLF，ZIP 文件名及源码路径包含中文和空格。

本次结果：

| 检查 | 结果 |
| --- | --- |
| Windows 主机通过 Nginx API 上传 ZIP | 通过 |
| Windows 绑定目录上的源码快照与 CodeQL 建库 | 通过，抽取 1/1 个 Python 文件 |
| CodeQL 固定扫描套件 | 完成，43 个查询，检出 1 条 `py/code-injection` |
| 真实 AI 初审 | 完成，检查 1/1 个窗口，模型调用 1 次，产生 2 个待确认候选 |
| 中文及空格路径源码预览 | 通过 |
| SARIF 下载 | 通过 |
| 浏览器页面 | 显示“初步审计完成”，未观察到 JS 错误 |
| API/Worker 强制重建 | 工具卷、队列、成功任务与 SARIF 保留，前端代理继续工作 |

AI 初审用量为 5,464 个输入 Token、1,558 个输出 Token。候选仍需复核；上述结果是流程兼容性证据，不是模型准确率或业务安全证明。

上传隔离、工作区、Windows 抽取配置、双引擎状态及工具解压边界的定向 pytest 回归通过。测试日志中仍有上游重复 OpenAPI operation ID 警告，不影响本次流程。

## 边界

本次未验证隔离修复、项目级修复前后对照、完整规则生成/发布、向量检索、JS 实际扫描、ARM 或 Windows 原生容器。基础 Compose 未挂载 Docker socket，隔离修复需要额外适配 CLI/引擎和同级容器文件路径。

密钥仅来自本地 `.env`；真实上传、执行产物、模型输出和本地安装包不随此次兼容性提交发布。详细启动、停止及工具准备命令见根目录 `DOCKER.md`。
