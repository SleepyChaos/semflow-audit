import { expect, test } from "@playwright/test"
import { audit, candidate, evidence, mockAuditApi } from "./fixtures/audit-api"

test("较早任务不在最新列表中仍能通过直接链接和刷新访问", async ({ page }) => {
  await mockAuditApi(page, { "/audits/": [] })
  await page.route("**/api/v1/audits/task-1", (route) =>
    route.fulfill({ json: audit }),
  )
  await page.goto("/audits/task-1?stage=review")
  await expect(
    page.getByRole("heading", { name: "AI 复审", exact: true }),
  ).toBeVisible()
  await expect(page.locator(".sidebar-project strong")).toHaveText(
    audit.project_name,
  )
  await page.reload()
  await expect(
    page.getByRole("heading", { name: "AI 复审", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText(candidate.title, { exact: true }).first(),
  ).toBeVisible()
})

test("扫描完成后刷新最终候选，不把刚生成的候选保留为零", async ({ page }) => {
  let completed = false
  await mockAuditApi(page)
  await page.route("**/api/v1/audits/", (route) =>
    route.fulfill({
      json: [{ ...audit, status: completed ? "completed" : "running" }],
    }),
  )
  await page.route("**/api/v1/audits/task-1/candidates", async (route) => {
    const final = completed
    await route.fulfill({ json: final ? [candidate] : [] })
    completed = true
  })
  await page.goto("/audits")
  const row = page.getByRole("row").filter({ hasText: audit.project_name })
  await expect(row.getByTestId("ai-count")).toHaveText("0")
  await expect(row.getByText("扫描完成", { exact: true })).toBeVisible({
    timeout: 8000,
  })
  await expect(row.getByTestId("ai-count")).toHaveText("1", { timeout: 6000 })
})

test("复核完成后读取最终候选与证据，即使轮询间隔尚未到达", async ({ page }) => {
  let completed = false
  await mockAuditApi(page)
  await page.route("**/api/v1/audits/task-1", (route) =>
    route.fulfill({ json: audit }),
  )
  await page.route("**/api/v1/audits/task-1/stages", (route) =>
    route.fulfill({
      json: [
        {
          id: "review-stage",
          audit_id: audit.id,
          kind: "review",
          status: completed ? "completed" : "running",
          checkpoint: "review",
          params: {},
          result: {},
          created_at: audit.created_at,
        },
      ],
    }),
  )
  await page.route("**/api/v1/audits/task-1/candidates", async (route) => {
    const final = completed
    await route.fulfill({ json: final ? [candidate] : [] })
    completed = true
  })
  await page.route("**/api/v1/audits/task-1/evidence", (route) =>
    route.fulfill({
      json: completed ? [evidence] : [],
    }),
  )
  await page.goto("/audits/task-1?stage=review")
  await expect(page.locator(".candidate-option")).toHaveCount(1, {
    timeout: 10000,
  })
  await expect(page.locator(".candidate-card pre").first()).toContainText(
    "return request.args",
  )
})

test("部分失败时保留已完成 CodeQL 的告警数", async ({ page }) => {
  const partial = { ...audit, status: "failed", phase: "discovery_partial" }
  await mockAuditApi(page, { "/audits/": [partial] })
  await page.route("**/api/v1/audits/task-1", (route) =>
    route.fulfill({ json: partial }),
  )
  await page.goto("/audits/task-1?stage=scan")
  await expect(
    page
      .locator(".task-summary-strip > span")
      .filter({ hasText: "静态告警" })
      .locator("strong"),
  ).toHaveText("0")
})
