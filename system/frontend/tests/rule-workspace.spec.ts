import { expect, test } from "@playwright/test"
import { mockAuditApi } from "./fixtures/audit-api"

const rule = {
  id: "rule-1",
  audit_id: "task-1",
  stage_id: "stage-1",
  title: "Flask 路由 XSS 检测",
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
test("生成条件与缺少材料均直接说明", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/stages": [
      {
        id: "s",
        kind: "rule",
        status: "failed",
        phase: "queued",
        created_at: "2026-10-11",
        result: { failure: { code: "materials_missing" } },
        error: "reference 没有匹配版本材料，需先补知识/范例",
        model: null,
        usage: {},
        inputs: {},
      },
    ],
  })
  await page.goto("/audits/task-1?stage=rules")
  await expect(
    page.getByText("选择真实漏洞，或填写明确的源码范围", { exact: true }),
  ).toBeVisible()
  await expect(page.getByText("缺少匹配版本的参考材料或规则范例")).toBeVisible()
  await page.getByRole("link", { name: "补充知识材料" }).click()
  await expect(page).toHaveURL(/knowledge\?auditId=task-1/)
})
test("未通过验收不能发布；发布规则可用于新审计", async ({ page }) => {
  await mockAuditApi(page, { "/rules/": [rule] })
  await page.goto("/rules")
  await expect(
    page
      .locator(".rule-validation-grid > div")
      .filter({ hasText: "独立测试" })
      .getByText("未运行"),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "完成全部验收后可发布" }),
  ).toBeDisabled()
  await page.unroute("**/api/v1/**")
  await mockAuditApi(page, { "/rules/": [{ ...rule, status: "published" }] })
  await page.reload()
  await page.getByRole("link", { name: "用于新审计" }).click()
  await expect(page).toHaveURL(/audits\/new\?ruleId=rule-1/)
})
test("草稿只有执行等待确认时才显示样本批准", async ({ page }) => {
  await mockAuditApi(page, {
    "/rules/": [rule],
    "/audits/task-1/stages": [
      { id: "stage-1", kind: "rule", status: "failed" },
    ],
  })
  await page.goto("/rules")
  await expect(page.getByRole("heading", { name: rule.title })).toBeVisible()
  await expect(
    page.getByRole("button", { name: "批准样本并运行真实验收" }),
  ).toHaveCount(0)
  await page.unroute("**/api/v1/**")
  await mockAuditApi(page, {
    "/rules/": [rule],
    "/audits/task-1/stages": [
      { id: "stage-1", kind: "rule", status: "awaiting_confirmation" },
    ],
  })
  await page.reload()
  await expect(
    page.getByRole("button", { name: "批准样本并运行真实验收" }),
  ).toBeVisible()
})
test("样本批准和项目根因确认保留各自接口参数", async ({ page }) => {
  const replay = {
    status: "candidate_match_needs_confirmation",
    matched_ids: ["finding-1"],
    baseline_matching_ids: [],
    findings: [
      {
        id: "finding-1",
        message: "raw payload",
        locations: [{ file: "app.py", line: 7 }],
        code_flows: [],
      },
    ],
  }
  await mockAuditApi(page, {
    "/rules/": [
      { ...rule, validation: { compile: "passed", project_replay: replay } },
    ],
    "/audits/task-1/stages": [
      { id: "stage-1", kind: "rule", status: "awaiting_confirmation" },
    ],
  })
  await page.goto("/rules")
  await page.getByLabel("样本确认理由").fill("已核实正例报警且转义反例不报警")
  const approval = page.waitForRequest((r) =>
    r.url().endsWith("/rule-1/approve-fixtures"),
  )
  await page.getByRole("button", { name: "批准样本并运行真实验收" }).click()
  expect((await approval).postDataJSON()).toEqual({
    reason: "已核实正例报警且转义反例不报警",
  })
  await page.getByLabel("对应目标根因的结果").selectOption("finding-1")
  await page
    .getByLabel("根因与路径确认依据")
    .fill("请求参数到未转义HTML响应的路径相同")
  const confirmation = page.waitForRequest((r) =>
    r.url().endsWith("/rule-1/confirm-project-match"),
  )
  await page.getByRole("button", { name: "确认新规则补上此漏洞" }).click()
  expect((await confirmation).postDataJSON()).toEqual({
    finding_id: "finding-1",
    reason: "请求参数到未转义HTML响应的路径相同",
  })
})
