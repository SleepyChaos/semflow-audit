import { expect, test } from "@playwright/test"
import { candidate, mockAuditApi } from "./fixtures/audit-api"

const cases = [
  {
    name: "test_security",
    category: "security",
    candidate_ids: ["candidate-1"],
    input_description: "带脚本标签的输入",
    expected_behavior: "应显示为普通文本",
    before: "assertion_failed",
    after: "passed",
    before_label: "断言未通过",
    after_label: "通过",
    reason: "原始风险已复现，补丁后阻断",
  },
  {
    name: "test_normal",
    category: "functional",
    candidate_ids: [],
    input_description: "普通中文输入",
    expected_behavior: "应保持原有文字",
    before: "passed",
    after: "passed",
    before_label: "通过",
    after_label: "通过",
    reason: "正常功能前后均通过",
  },
]
const comparison = {
  status: "passed",
  stage_id: "comparison-1",
  receipt_hash: "receipt-1",
  summary: "所列前后对比通过",
  repetitions: 2,
  cases,
}
const record = {
  id: "repair-1",
  stage_id: "repair-stage",
  candidate_ids: ["candidate-1"],
  changes: [],
  validation: { isolated_tests: { status: "passed", profile: "syntax" } },
  status: "needs_review",
  acceptance_reason: null,
  acceptance_ready: true,
  comparison,
}
const suite = {
  id: "suite-1",
  image: "project-validator:local",
  candidate_ids: ["candidate-1"],
  suite_hash: "fixed-hash-12345678",
  snapshot_hash: "snapshot",
  test_files_hash: "files",
  origin: "imported",
  suite: {
    title: "这个项目的独立验收",
    summary: "检查安全和正常功能",
    language: "python",
    files: { "test_check.py": "# team reviewed tests" },
    cases,
    assumptions: [],
  },
}

test("按当前测试证据接受，并显示中文前后对比", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/repairs": [record],
    "/audits/task-1/candidates": [{ ...candidate, status: "confirmed" }],
  })
  await page.goto("/audits/task-1?stage=repair")
  await expect(page.getByText("已复现风险")).toBeVisible()
  await expect(page.getByText("普通中文输入")).toBeVisible()
  const accept = page.getByRole("button", { name: "接受此补丁" })
  await page.getByLabel("补丁审阅理由").fill("已审阅测试输入、断言和补丁改动")
  await expect(accept).toBeDisabled()
  await page.getByRole("checkbox", { name: "已审阅测试断言和前后结果" }).check()
  const sent = page.waitForRequest(
    (r) =>
      r.url().endsWith("/repairs/repair-1/accept") && r.method() === "POST",
  )
  await accept.click()
  expect((await sent).postDataJSON()).toEqual({
    reason: "已审阅测试输入、断言和补丁改动",
    comparison_stage_id: "comparison-1",
    test_reviewed: true,
  })
})

test("语法通过以及未复现的测试不能开放接受入口", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/repairs": [
      {
        ...record,
        acceptance_ready: false,
        comparison: {
          ...comparison,
          status: "inconclusive",
          summary: "原代码也通过，没有复现漏洞",
          cases: [
            { ...cases[0], before: "passed", before_label: "通过" },
            cases[1],
          ],
        },
      },
    ],
  })
  await page.goto("/audits/task-1?stage=repair")
  await expect(page.getByText("验证证据不足")).toBeVisible()
  await expect(page.getByRole("button", { name: "接受此补丁" })).toHaveCount(0)
})

test("选择项目测试集后，补丁请求携带固定测试身份", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/verification-suites": [suite],
    "/audits/task-1/candidates": [{ ...candidate, status: "confirmed" }],
  })
  await page.goto("/audits/task-1?stage=repair")
  await expect(
    page.getByRole("button", { name: "AI 生成验收测试草案" }),
  ).toBeDisabled()
  await page
    .getByRole("checkbox", { name: candidate.title, exact: true })
    .check()
  await page.getByLabel("选择项目验收测试集").selectOption("suite-1")
  const sent = page.waitForRequest(
    (r) => r.url().endsWith("/task-1/repair") && r.method() === "POST",
  )
  await page.getByRole("button", { name: "生成并验证修复 Diff" }).click()
  expect((await sent).postDataJSON().verification_suite_id).toBe("suite-1")
})

test("重跑得到新验证结果后，旧审阅勾选失效", async ({ page }) => {
  let current = record
  await mockAuditApi(page, {
    "/audits/task-1/verification-suites": [suite],
    "/audits/task-1/candidates": [{ ...candidate, status: "confirmed" }],
  })
  await page.route("**/audits/task-1/repairs", (route) =>
    route.fulfill({ json: [current] }),
  )
  await page.route("**/repairs/repair-1/verify", async (route) => {
    current = {
      ...record,
      comparison: {
        ...comparison,
        stage_id: "comparison-2",
        receipt_hash: "receipt-2",
      },
    }
    await route.fulfill({
      status: 201,
      json: { id: "comparison-2", kind: "verification", status: "completed" },
    })
  })
  await page.goto("/audits/task-1?stage=repair")
  await page
    .getByRole("checkbox", { name: candidate.title, exact: true })
    .check()
  await page.getByLabel("选择项目验收测试集").selectOption("suite-1")
  await page.getByLabel("补丁审阅理由").fill("已经审阅旧的前后对比和测试断言")
  const review = page.getByRole("checkbox", {
    name: "已审阅测试断言和前后结果",
  })
  await review.check()
  await expect(page.getByRole("button", { name: "接受此补丁" })).toBeEnabled()
  await page.getByRole("button", { name: "运行修复前后对比" }).click()
  await expect(review).not.toBeChecked()
  await expect(page.getByRole("button", { name: "接受此补丁" })).toBeDisabled()
})
