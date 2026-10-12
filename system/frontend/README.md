# Frontend

React + Vite + TanStack Router/Query + shadcn/ui。使用 `npm ci`、`npm run dev` 和 `npm run build`。

开发服务代理 `/api` 到本地 8000 端口。审计业务位于 src/features 与 src/api；本地工具无需登录，所有请求通过 src/api 使用同源 `/api/v1` 接口。

完整启动与验证步骤参阅根目录 README.md。

`/login` 为免账号欢迎页，点击“进入工作台”即可进入 `/` 审计界面；入口提供浅色/深色主题切换。`/` 可直接访问，不需要令牌或账号。

端到端验证：`npm test`。使用现有本地服务可设置 `PLAYWRIGHT_BASE_URL`；若使用已安装的 Chrome 而非 Playwright 浏览器，可设置 `PLAYWRIGHT_CHANNEL=chrome`。测试从空浏览器存储开始，不读取账号或密码。
