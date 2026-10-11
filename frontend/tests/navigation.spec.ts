import { expect, test } from "@playwright/test"
import { mockAuditApi } from "./fixtures/audit-api"

test.beforeEach(async ({ page }) => mockAuditApi(page))
test("四阶段左侧导航保持任务、刷新和后退", async ({ page }) => {
  await page.goto("/audits/task-1?stage=review")
  await expect(
    page.getByRole("heading", { name: "AI 复审", exact: true }),
  ).toBeVisible()
  const sidebar = page.getByRole("navigation", { name: "主导航" })
  await expect(
    sidebar.getByRole("link", { name: "AI 复审", exact: true }),
  ).toHaveAttribute("aria-current", "page")
  await sidebar.getByRole("link", { name: "RAG 规则", exact: true }).click()
  await expect(page).toHaveURL(/audits\/task-1\?stage=rules/)
  await page.reload()
  await expect(
    sidebar.getByRole("link", { name: "RAG 规则", exact: true }),
  ).toHaveAttribute("aria-current", "page")
  await page.goBack()
  await expect(page).toHaveURL(/stage=review/)
  await expect(
    page.getByRole("heading", { name: "AI 复审", exact: true }),
  ).toBeVisible()
})
test("全局页面和无效任务可直接访问", async ({ page }) => {
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "审计总览", exact: true }),
  ).toBeVisible()
  await page
    .getByRole("navigation", { name: "主导航" })
    .getByRole("link", { name: "知识库", exact: true })
    .click()
  await expect(
    page.getByRole("heading", { name: "知识库", exact: true }),
  ).toBeVisible()
  await page.goto("/audits/missing?stage=review")
  await expect(page.getByText("未找到审计任务", { exact: true })).toBeVisible()
})
