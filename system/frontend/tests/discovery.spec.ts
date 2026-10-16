import { expect, test } from "@playwright/test"
import { audit, candidate, evidence, mockAuditApi } from "./fixtures/audit-api"

const scout = {
  id: "stage-1",
  audit_id: audit.id,
  kind: "scout",
  status: "completed",
  phase: "hypotheses_ready",
  created_at: audit.created_at,
  updated_at: audit.created_at,
  inputs: {},
  error: null,
  model_calls: [{}, {}],
  result: {
    units: [{ unit_id: "unit-1", status: "inspected" }],
    coverage: {
      status: "partial",
      planned_windows: 3,
      inspected_windows: 1,
      uninspected_windows: 2,
      stop_reason: "budget_exhausted",
      files: [{ file: "app.py", total_windows: 3, inspected_windows: 1 }],
    },
  },
}
const finding = {
  id: "finding-1",
  rule: "py/reflective-xss",
  message: "输入直接返回到 HTML",
  locations: [{ file: "app.py", line: 7, column: 1, end_line: 7 }],
  code_flows: [],
  assessment: "pending",
}

test("同页展示 AI 部分覆盖和候选，仅读取当前阶段与快照证据", async ({
  page,
}) => {
  await mockAuditApi(page, {
    "/audits/task-1": { ...audit, findings: [finding] },
    "/audits/task-1/stages": [scout],
    "/audits/task-1/candidates": [
      candidate,
      { ...candidate, id: "old", stage_id: "old-stage", title: "旧执行候选" },
      {
        ...candidate,
        id: "other",
        audit_id: "other-task",
        title: "其他任务候选",
      },
    ],
    "/audits/task-1/evidence": [
      evidence,
      { ...evidence, stage_id: "old-stage", content: "错误阶段证据" },
      { ...evidence, snapshot_hash: "wrong", content: "错误快照证据" },
    ],
    "/audits/task-1/source": {
      file: "app.py",
      start_line: 7,
      lines: ["return request.args['payload']"],
    },
  })
  await page.goto("/audits/task-1?stage=scan")
  const ai = page.getByLabel("AI 初审", { exact: true })
  await expect(ai.getByText("部分完成", { exact: true }).first()).toBeVisible()
  await expect(ai.getByText("1 / 3", { exact: true })).toBeVisible()
  await expect(ai.getByText(/模型调用预算耗尽/)).toBeVisible()
  await expect(ai.getByText(/2 个窗口未检查/)).toBeVisible()
  await expect(ai.getByText("旧执行候选")).toHaveCount(0)
  await expect(ai.getByText("其他任务候选")).toHaveCount(0)
  await ai.getByRole("button", { name: new RegExp(candidate.title) }).click()
  const detail = page.getByRole("article", { name: "AI 候选详情" })
  await expect(
    detail.getByText(candidate.description, { exact: true }),
  ).toBeVisible()
  await expect(detail.locator("pre")).toContainText(
    "return request.args['payload']",
  )
  await expect(detail.getByText("错误阶段证据")).toHaveCount(0)
  await expect(detail.getByText("错误快照证据")).toHaveCount(0)
  const staticOption = page.getByRole("button", { name: /py\/reflective-xss/ })
  await expect(staticOption).toHaveAttribute("aria-pressed", "false")
  expect(
    await staticOption.evaluate(
      (element) => getComputedStyle(element).backgroundColor,
    ),
  ).not.toBe("rgba(0, 0, 0, 0)")
  await staticOption.focus()
  await page.keyboard.press("Enter")
  await expect(staticOption).toHaveAttribute("aria-pressed", "true")
  await expect(page.locator(".finding-detail pre")).toContainText(
    "return request.args",
  )
  await expect(
    page.getByRole("button", { name: "复核候选", exact: true }),
  ).toBeEnabled()
})

test("初始阶段列表为空时仍轮询，CodeQL 完成后持续更新 AI 并读取最终候选", async ({
  page,
}) => {
  await mockAuditApi(page)
  let stageReads = 0
  let complete = false
  await page.route("**/api/v1/audits/task-1", (route) =>
    route.fulfill({
      json: {
        ...audit,
        status: complete ? "completed" : "running",
        phase: "codeql_ready",
      },
    }),
  )
  await page.route("**/api/v1/audits/task-1/stages", (route) => {
    stageReads += 1
    return route.fulfill({
      json:
        stageReads === 1
          ? []
          : [
              {
                ...scout,
                status: complete ? "completed" : "running",
                phase: complete ? "hypotheses_ready" : "scout_windows",
                result: complete
                  ? scout.result
                  : { units: [{ unit_id: "unit-1", status: "inspected" }] },
              },
            ],
    })
  })
  await page.route("**/api/v1/audits/task-1/candidates", (route) =>
    route.fulfill({ json: complete ? [candidate] : [] }),
  )
  await page.goto("/audits/task-1?stage=scan")
  const ai = page.getByLabel("AI 初审", { exact: true })
  await expect(ai.getByText("正在执行", { exact: true })).toBeVisible({
    timeout: 10000,
  })
  await expect(ai.getByText(/AI 初审正在执行，尚未保存候选/)).toBeVisible()
  await expect(
    page.getByRole("button", { name: "复核候选", exact: true }),
  ).toBeDisabled()
  await expect(
    ai.getByRole("button", { name: "进入 AI 复审", exact: true }),
  ).toHaveCount(0)
  complete = true
  await expect(ai.getByText("部分完成", { exact: true }).first()).toBeVisible({
    timeout: 10000,
  })
  await expect(
    ai.getByRole("button", { name: new RegExp(candidate.title) }),
  ).toBeVisible({ timeout: 10000 })
  const review = page.getByRole("button", { name: "复核候选", exact: true })
  await expect(review).toBeEnabled({ timeout: 10000 })
  await expect(
    ai.getByRole("button", { name: "进入 AI 复审", exact: true }),
  ).toHaveCount(0)
  await review.click()
  await expect(page).toHaveURL(/stage=review/)
})

test("候选读取失败不展示正常零候选，重试恢复结果", async ({ page }) => {
  await mockAuditApi(page, { "/audits/task-1/stages": [scout] })
  let failed = true
  await page.route("**/api/v1/audits/task-1/candidates", (route) =>
    route.fulfill(
      failed
        ? { status: 500, json: { detail: "测试读取失败" } }
        : { json: [candidate] },
    ),
  )
  await page.goto("/audits/task-1?stage=scan")
  const ai = page.getByLabel("AI 初审", { exact: true })
  await expect(ai.getByText("AI 候选读取失败", { exact: true })).toBeVisible()
  await expect(ai.getByText("无法读取", { exact: true })).toBeVisible()
  await expect(ai.getByText(/已检查范围暂无已保存候选/)).toHaveCount(0)
  failed = false
  await ai.getByRole("button", { name: "重新读取候选" }).click()
  await expect(
    ai.getByRole("button", { name: new RegExp(candidate.title) }),
  ).toBeVisible()
})

test("阶段读取失败不冒充初审未执行，恢复后展示实际部分完成", async ({
  page,
}) => {
  await mockAuditApi(page)
  let failed = true
  await page.route("**/api/v1/audits/task-1/stages", (route) =>
    route.fulfill(
      failed
        ? { status: 500, json: { detail: "阶段读取失败" } }
        : { json: [scout] },
    ),
  )
  await page.goto("/audits/task-1?stage=scan")
  const ai = page.getByLabel("AI 初审", { exact: true })
  await expect(
    ai.getByText("AI 执行状态读取失败", { exact: true }),
  ).toBeVisible({ timeout: 10000 })
  await expect(ai.getByText(/该任务未运行 AI 初审/)).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "复核候选", exact: true }),
  ).toBeDisabled()
  failed = false
  await ai.getByRole("button", { name: "重新读取状态" }).click()
  await expect(ai.getByText("部分完成", { exact: true }).first()).toBeVisible()
})

test("AI 已结束但 CodeQL 仍在运行时复核入口保持禁用，汇总后自动开放", async ({
  page,
}) => {
  await mockAuditApi(page, { "/audits/task-1/stages": [scout] })
  let scanning = true
  await page.route("**/api/v1/audits/task-1", (route) =>
    route.fulfill({
      json: {
        ...audit,
        status: scanning ? "running" : "completed",
        phase: scanning ? "scan" : "discovery_partial",
        coverage: {
          dual_engine: {
            status: scanning ? "running" : "partial",
            codeql: { status: scanning ? "running" : "completed" },
            scout: { status: "completed", stage_id: scout.id },
          },
        },
      },
    }),
  )
  await page.goto("/audits/task-1?stage=scan")
  const review = page.getByRole("button", { name: "复核候选", exact: true })
  await expect(
    page.getByText("等待 CodeQL 静态分析结束后复核。", { exact: true }).first(),
  ).toBeVisible()
  await expect(review).toBeDisabled()
  await expect(
    page.getByRole("button", { name: "进入 AI 复审", exact: true }),
  ).toHaveCount(0)
  scanning = false
  await expect(review).toBeEnabled({ timeout: 10000 })
  await expect(
    page.getByRole("button", { name: "进入 AI 复审", exact: true }),
  ).toHaveCount(0)
})

test("历史静态任务明确标注初审未执行，窄屏不横向溢出", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1": { ...audit, coverage: {}, findings: [finding] },
    "/audits/task-1/candidates": [],
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/audits/task-1?stage=scan")
  await expect(page.getByText(/该任务未运行 AI 初审/)).toBeVisible()
  await expect(
    page.getByRole("button", { name: /py\/reflective-xss/ }),
  ).toBeVisible()
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy()
})
