import { expect, test } from "@playwright/test"

test("空浏览器直接进入工作台，刷新仍不需要登录", async ({ page }) => {
  const errors: string[] = []
  const requests: string[] = []
  const authHeaders: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) {
      requests.push(request.url())
      if (request.headers().authorization) authHeaders.push(request.url())
    }
  })
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "审计总览", exact: true }),
  ).toBeVisible()
  await page.getByRole("button", {name: /本地环境/}).click()
  await expect(page.getByRole("heading", {name: "执行环境", exact:true})).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByText("无法读取审计任务", { exact: true })).toHaveCount(
    0,
  )
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/audits/") && response.status() === 200,
  )
  await page.getByRole("button", { name: "刷新", exact: true }).click()
  await response
  await page.reload()
  await expect(
    page.getByRole("heading", { name: "审计总览", exact: true }),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText("退出登录", { exact: true })).toHaveCount(0)
  expect(requests.some((url) => url.endsWith("/api/v1/audits/"))).toBeTruthy()
  expect(requests.some((url) => /\/(users|login)\//.test(url))).toBeFalsy()
  expect(authHeaders).toEqual([])
  expect(errors).toEqual([])
})

test("欢迎页点击按钮进入工作台，无账号输入或认证请求", async ({ page }) => {
  const authRequests: string[] = []
  page.on("request", (request) => {
    if (/\/api\/v1\/(users|login)\//.test(request.url())) {
      authRequests.push(request.url())
    }
  })
  await page.goto("/login")
  await expect(page).toHaveURL(/\/login$/)
  await expect(
    page.getByRole("heading", { name: "进入审计工作台" }),
  ).toBeVisible()
  await expect(page.getByRole("textbox")).toHaveCount(0)
  await expect(page.locator("input")).toHaveCount(0)
  await page.getByRole("button", { name: "进入工作台", exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(
    page.getByRole("heading", { name: "审计总览", exact: true }),
  ).toBeVisible()
  expect(authRequests).toEqual([])
})

test("欢迎页支持主题切换、移动布局和键盘进入", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto("/login")
  await page.getByRole("button", { name: "切换到深色主题" }).click()
  await expect(page.locator("html")).toHaveClass(/dark/)
  await page.reload()
  await expect(
    page.getByRole("button", { name: "切换到浅色主题" }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy()
  const enter = page.getByRole("button", { name: "进入工作台", exact: true })
  await expect(enter).toBeInViewport()
  await enter.focus()
  await page.keyboard.press("Enter")
  await expect(page).toHaveURL(/\/$/)
  await expect(
    page.getByRole("heading", { name: "审计总览", exact: true }),
  ).toBeVisible()
})

test("接口失败显示真实错误并保留当前工作台", async ({ page }) => {
  await page.route("**/api/v1/audits/", (route) =>
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "本地接口测试错误" }),
    }),
  )
  await page.goto("/")
  await expect(page.getByRole("alert").filter({hasText:"本地接口测试错误"})).toBeVisible(
    { timeout: 15000 },
  )
  await expect(page).toHaveURL(/\/$/)
  await expect(
    page.getByRole("heading", { name: "审计总览", exact: true }),
  ).toBeVisible()
})
