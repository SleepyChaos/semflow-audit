# Frontend

React + Vite + TanStack Router/Query + shadcn/ui。使用 `npm ci`、`npm run dev` 和 `npm run build`。

Vite 开发服务默认在 5174 端口，代理 `/api` 到本地 8001 端口，可通过 `SEMFLOW_API_PROXY` 覆盖代理目标。完整 Docker 模式由 Nginx 代理到 `backend:8000`。审计业务位于 src/features 与 src/api；本地工具无需登录，所有请求通过 src/api 使用同源 `/api/v1` 接口。

完整服务启动见 [Docker 启动说明](../../DOCKER.md)，主机调试见[主机开发环境补充](../collaborator-setup.md)，验证见[系统说明](../README.md#代码与-cli-验证)。

`/login` 为免账号欢迎页，点击“进入工作台”即可进入 `/` 审计界面；入口提供浅色/深色主题切换。`/` 可直接访问，不需要令牌或账号。

端到端验证：`npm test`。使用现有本地服务可设置 `PLAYWRIGHT_BASE_URL`；若使用已安装的 Chrome 而非 Playwright 浏览器，可设置 `PLAYWRIGHT_CHANNEL=chrome`。测试从空浏览器存储开始，不读取账号或密码。
