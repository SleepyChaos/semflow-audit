import { expect, test } from "@playwright/test"
import { candidate, mockAuditApi } from "./fixtures/audit-api"

test("仅待确认候选可导出报告，但必须先确认再修复", async ({ page }) => {
  await mockAuditApi(page)
  await page.goto("/audits/task-1?stage=repair")
  await expect(
    page.getByRole("button", { name: "导出 Markdown 报告" }),
  ).toBeEnabled()
  await expect(
    page.getByRole("button", { name: "生成并验证修复 Diff" }),
  ).toBeDisabled()
  await expect(page.getByText("先确认缺陷")).toBeVisible()
  await page.getByRole("link", { name: "前往 AI 复审" }).click()
  await expect(page).toHaveURL(/stage=review/)
})
test("选择确认候选发送隔离验证选项和 ID", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [{ ...candidate, status: "confirmed" }],
  })
  await page.goto("/audits/task-1?stage=repair")
  await page
    .getByRole("checkbox", { name: candidate.title, exact: true })
    .check()
  await expect(page.getByText("已选择 1 个已确认缺陷")).toBeVisible()
  const sent = page.waitForRequest(
    (r) => r.url().endsWith("/task-1/repair") && r.method() === "POST",
  )
  await page.getByRole("button", { name: "生成并验证修复 Diff" }).click()
  expect((await sent).postDataJSON()).toEqual({
    candidate_ids: ["candidate-1"],
    allowed_paths: [],
    validation_profile: "syntax",
    rescan: true,
  })
})
test("报告未生成补丁即可下载；接受失败保留审阅理由", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/repairs": [
      {
        id: "repair-1",
        stage_id: "stage-1",
        candidate_ids: ["candidate-1"],
        changes: [],
        validation: {},
        status: "checks_passed",
        acceptance_ready: true,
        comparison: {
          status: "passed",
          stage_id: "comparison-1",
          receipt_hash: "receipt-1",
          summary: "所列前后测试已通过",
          cases: [],
          repetitions: 2,
        },
        acceptance_reason: null,
      },
    ],
  })
  await page.goto("/audits/task-1?stage=repair")
  const report = page.waitForEvent("download")
  await page.getByRole("button", { name: "导出 JSON 报告" }).click()
  expect((await report).suggestedFilename()).toBe("task-1-report.json")
  await page.route("**/repairs/repair-1/accept", (route) =>
    route.fulfill({ status: 409, json: { detail: "验证结果已变化" } }),
  )
  await page
    .getByLabel("补丁审阅理由")
    .fill("已核实修改和语法验证但尚需人工复核")
  await page.getByRole("checkbox", { name: "已审阅测试断言和前后结果" }).check()
  await page.getByRole("button", { name: "接受此补丁" }).click()
  await expect(
    page.getByRole("alert").filter({ hasText: "验证结果已变化" }).first(),
  ).toBeVisible()
  await expect(page.getByLabel("补丁审阅理由")).toHaveValue(
    "已核实修改和语法验证但尚需人工复核",
  )
})
