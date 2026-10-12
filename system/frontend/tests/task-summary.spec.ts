import { expect, test } from "@playwright/test"
import { audit, candidate, mockAuditApi } from "./fixtures/audit-api"

test("列表分别呈现静态告警、AI 候选和人工确认", async ({ page }) => {
  await mockAuditApi(page)
  await page.goto("/audits")
  const row = page.getByRole("row").filter({ hasText: audit.project_name })
  await expect(
    page.getByRole("columnheader", { name: "AI 候选", exact: true }),
  ).toBeVisible()
  await expect(row.getByTestId("static-count")).toHaveText("0")
  await expect(row.getByTestId("ai-count")).toHaveText("1")
  await expect(row.getByTestId("confirmed-count")).toHaveText("0")
})
test("读取失败不计零；已有人工决定优先于同身份待确认", async ({ page }) => {
  await mockAuditApi(page, { "/audits/task-1/candidates": "ERROR" })
  await page.goto("/audits")
  await expect(page.getByTestId("ai-count")).toHaveText("无法读取")
  await page.unroute("**/api/v1/**")
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [
      { ...candidate, id: "confirmed-1", status: "confirmed" },
      candidate,
    ],
  })
  await page.reload()
  await expect(page.getByTestId("confirmed-count")).toHaveText("1")
  await expect(page.getByTestId("ai-count")).toHaveText("1")
  await page.getByLabel("搜索项目").fill("不存在")
  await expect(page.getByText("没有符合筛选条件的任务")).toBeVisible()
})
test("新建上传使用真实返回 ID，保留语言和项目名", async ({ page }) => {
  await mockAuditApi(page)
  await page.route("**/api/v1/audits/", async (route) => {
    if (route.request().method() === "POST") {
      expect(route.request().postData()).toContain("demo-project")
      await route.fulfill({ json: { ...audit, id: "task-1" } })
    } else await route.fulfill({ json: [audit] })
  })
  await page.goto("/audits/new")
  await page.getByLabel("项目名称（可选）").fill("demo-project")
  await page.getByLabel("选择代码包").setInputFiles({
    name: "example.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("test"),
  })
  await page.getByRole("button", { name: "开始审计", exact: true }).click()
  await expect(page).toHaveURL(/audits\/task-1\?stage=scan/)
})
