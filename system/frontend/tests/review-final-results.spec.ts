import { expect, test } from "@playwright/test"
import { audit, candidate, mockAuditApi } from "./fixtures/audit-api"

for (const previous of ["insufficient", "excluded"]) {
  test(`同身份 ${previous} 旧记录不遮住后来的确认，修复和规则均可选择`, async ({
    page,
  }) => {
    await mockAuditApi(page, {
      "/audits/task-1/candidates": [
        { ...candidate, id: "older", status: previous },
        { ...candidate, id: "newer", status: "confirmed" },
      ],
    })
    await page.goto("/audits")
    await expect(page.getByTestId("confirmed-count")).toHaveText("1")
    await page.goto("/audits/task-1?stage=repair")
    await expect(
      page.getByRole("checkbox", { name: candidate.title, exact: true }),
    ).toBeVisible()
    await page.goto("/audits/task-1?stage=rules")
    await expect(
      page.getByLabel("提炼已确认缺陷").locator('option[value="newer"]'),
    ).toHaveCount(1)
  })
}

test("同身份相互冲突的人工判断按实际判断时间取最新，保留原始记录", async ({
  page,
}) => {
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [
      { ...candidate, id: "older", status: "confirmed" },
      { ...candidate, id: "newer", status: "excluded" },
    ],
    "/candidates/older/decisions": [
      { status: "confirmed", created_at: "2026-10-11T08:00:00Z" },
    ],
    "/candidates/newer/decisions": [
      { status: "excluded", created_at: "2026-10-11T09:00:00Z" },
    ],
  })
  await page.goto("/audits")
  await expect(page.getByTestId("confirmed-count")).toHaveText("0")
  await page.goto("/audits/task-1?stage=review")
  await expect(page.locator(".candidate-option")).toHaveCount(1)
  await expect(
    page
      .locator(".candidate-card header")
      .getByText("支持排除", { exact: true }),
  ).toBeVisible()
  await page
    .getByText("全部原始候选记录与复核历史（未删除或按根因合并）", {
      exact: true,
    })
    .click()
  await expect(
    page.locator("pre").filter({ hasText: '"id": "newer"' }).first(),
  ).toBeVisible()
  // The older candidate can carry the newer judgment; creation order is not
  // decision order.
  await page.unroute("**/api/v1/**")
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [
      { ...candidate, id: "older", status: "excluded" },
      { ...candidate, id: "newer", status: "confirmed" },
    ],
    "/candidates/older/decisions": [
      { status: "excluded", created_at: "2026-10-11T09:00:00Z" },
    ],
    "/candidates/newer/decisions": [
      { status: "confirmed", created_at: "2026-10-11T08:00:00Z" },
    ],
  })
  await page.goto("/audits")
  await expect(page.getByTestId("confirmed-count")).toHaveText("0")
})

test("修复结束后立即读取最终验证结果", async ({ page }) => {
  let completed = false
  await mockAuditApi(page)
  await page.route("**/api/v1/audits/task-1/stages", (route) =>
    route.fulfill({
      json: [
        {
          id: "stage-1",
          audit_id: audit.id,
          kind: "repair",
          status: completed ? "completed" : "running",
          phase: "validation",
          result: {},
          inputs: {},
          created_at: audit.created_at,
        },
      ],
    }),
  )
  await page.route("**/api/v1/audits/task-1/repairs", async (route) => {
    const status = completed ? "checks_passed" : "draft"
    await route.fulfill({
      json: [
        {
          id: "repair-1",
          stage_id: "stage-1",
          candidate_ids: [],
          changes: [],
          validation: {},
          status,
          acceptance_ready: completed,
          comparison: completed
            ? {
                status: "passed",
                stage_id: "comparison-1",
                receipt_hash: "receipt-1",
                summary: "所列对比已通过",
                cases: [],
                repetitions: 2,
              }
            : { status: "missing" },
          acceptance_reason: null,
        },
      ],
    })
    completed = true
  })
  await page.goto("/audits/task-1?stage=repair")
  await expect(
    page.getByText("前后对比通过，待人工接受", { exact: true }),
  ).toBeVisible({ timeout: 10000 })
  await expect(
    page.getByRole("button", { name: "接受此补丁", exact: true }),
  ).toBeVisible()
})

test("规则进入待人工确认后刷新最终草稿和样本批准入口", async ({ page }) => {
  let ready = false
  await mockAuditApi(page)
  await page.route("**/api/v1/audits/task-1/stages", (route) =>
    route.fulfill({
      json: [
        {
          id: "stage-1",
          audit_id: audit.id,
          kind: "rule",
          status: ready ? "awaiting_confirmation" : "running",
          phase: "development",
          result: {},
          inputs: {},
          created_at: audit.created_at,
        },
      ],
    }),
  )
  await page.route("**/api/v1/rules/?*", async (route) => {
    const rule = {
      id: "rule-1",
      audit_id: audit.id,
      stage_id: "stage-1",
      title: "最终 XSS 草稿",
      language: "python",
      purpose: "vulnerability_detector",
      holdout_id: null,
      strategy: "new_query",
      query: "import python",
      modules: {},
      query_hash: "abc",
      status: "draft",
      fixtures_approved: false,
      fixtures: {},
      validation: { compile: "passed" },
      retrieval: [],
    }
    const final = ready
    await route.fulfill({ json: final ? [rule] : [] })
    ready = true
  })
  await page.goto("/audits/task-1?stage=rules")
  await expect(
    page.getByRole("heading", { name: "最终 XSS 草稿", exact: true }),
  ).toBeVisible({ timeout: 10000 })
  await expect(
    page.getByRole("button", { name: "批准样本并运行真实验收" }),
  ).toBeVisible()
})
