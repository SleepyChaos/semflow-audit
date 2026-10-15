import { expect, test } from "@playwright/test"
import { candidate, mockAuditApi } from "./fixtures/audit-api"

const narrative = {
  overview: "这个项目的查询参数进入网页响应，需要检查转义。",
  issues: [
    {
      candidate_id: candidate.id,
      title: "查询参数进入 HTML 响应",
      explanation: "实际返回语句直接使用 payload 参数，没有进行转义。",
      impact: "浏览器可能将不可信输入当作脚本执行。",
      fix_suggestions: ["在 app.py 返回参数前调用 escape，保留正常文本显示。"],
      verification_suggestions: ["用正常文字和脚本输入分别比较修复前后。"],
      evidence_ids: ["evidence-1"],
    },
  ],
  repair_review: "尚未运行攻击测试，不能确认修复成功。",
  limitations: ["部署配置尚未验证。"],
  next_steps: ["先确认源码，再添加功能和安全测试。"],
}

test("首次导出为当前任务生成 AI 中文报告，成功后下载", async ({ page }) => {
  await mockAuditApi(page)
  let generated = false
  await page.route("**/api/v1/audits/task-1/report", (route) =>
    route.fulfill({
      json: {
        candidates: [candidate],
        ai_report: {
          status: generated ? "ready" : "missing",
          narrative: generated ? narrative : undefined,
          model: "test-model",
        },
      },
    }),
  )
  await page.route("**/api/v1/audits/task-1/report-analysis", (route) => {
    generated = true
    return route.fulfill({
      json: { id: "report-1", kind: "report", status: "queued" },
    })
  })
  await page.route("**/api/v1/audits/task-1/report.md", (route) =>
    route.fulfill({
      body: "# AI 中文报告\n具体修复建议",
      contentType: "text/markdown",
    }),
  )
  await page.goto("/audits/task-1?stage=report")
  await expect(
    page.getByRole("button", { name: "生成 AI 中文报告", exact: true }),
  ).toBeEnabled()
  const sent = page.waitForRequest((r) => r.url().endsWith("/report-analysis"))
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "导出 Markdown 报告" }).click()
  expect((await sent).postDataJSON()).toEqual({ force: false })
  expect((await download).suggestedFilename()).toBe("task-1-report.md")
  await expect(
    page.getByText(narrative.overview, { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText(narrative.issues[0].fix_suggestions[0], { exact: true }),
  ).toBeVisible()
})

test("AI 生成失败保留原因，不下载模板报告", async ({ page }) => {
  await mockAuditApi(page)
  let failed = false
  await page.route("**/api/v1/audits/task-1/report", (route) =>
    route.fulfill({
      json: {
        candidates: [candidate],
        ai_report: {
          status: failed ? "failed" : "missing",
          error: failed ? "模型服务请求失败" : null,
        },
      },
    }),
  )
  await page.route("**/api/v1/audits/task-1/report-analysis", (route) => {
    failed = true
    return route.fulfill({ json: { id: "report-1", status: "failed" } })
  })
  let downloads = 0
  page.on("download", () => downloads++)
  await page.goto("/audits/task-1?stage=report")
  await page.getByRole("button", { name: "导出 Markdown 报告" }).click()
  await expect(
    page.getByRole("alert").filter({ hasText: "报告生成失败" }),
  ).toBeVisible()
  expect(downloads).toBe(0)
  await expect(
    page.getByRole("button", { name: "生成 AI 中文报告", exact: true }),
  ).toBeEnabled()
})

test("AI 复审直接显示当前任务的 AI 中文修复建议", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [
      {
        ...candidate,
        explanation: {
          candidate_id: candidate.id,
          title: "通用标题",
          location: "app.py:7",
          status: "pending",
          observation: "通用类型描述",
          risk: "通用风险",
          remediation: "通用方向",
          next_step: "需要核实",
          boundary: "通用类型导读",
        },
      },
    ],
  })
  await page.route("**/api/v1/audits/task-1/report", (route) =>
    route.fulfill({
      json: {
        candidates: [candidate],
        ai_report: { status: "ready", narrative, model: "test-model" },
      },
    }),
  )
  await page.goto("/audits/task-1?stage=review")
  await expect(
    page.getByText("AI 中文分析与修复建议", { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText(narrative.issues[0].fix_suggestions[0], { exact: true }),
  ).toBeVisible()
  await expect(page.getByText("通用方向", { exact: true })).toHaveCount(0)
})

test("报告执行历史提供取消和详情入口", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/stages": [
      {
        id: "report-1",
        audit_id: "task-1",
        kind: "report",
        phase: "write_chinese_report",
        status: "running",
        inputs: {},
        result: {},
        created_at: "2026-10-11T08:00:00Z",
        model_config_snapshot: {},
        usage: {},
      },
    ],
  })
  await page.route("**/api/v1/audits/task-1/report", (route) =>
    route.fulfill({ json: { ai_report: { status: "running" } } }),
  )
  await page.goto("/audits/task-1?stage=report")
  await expect(
    page.getByRole("button", { name: "取消", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("button").filter({ hasText: "生成中文报告" }).last(),
  ).toBeVisible()
})
