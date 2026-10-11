import { expect, test } from "@playwright/test"
import { candidate, mockAuditApi } from "./fixtures/audit-api"

test("证据可见，理由和源码证据共同约束人工确认", async ({ page }) => {
  await mockAuditApi(page)
  await page.goto("/audits/task-1?stage=review")
  await expect(page.getByTestId("candidate-workspace")).toBeVisible()
  await expect(
    page.getByText("return request.args['payload']", { exact: false }).first(),
  ).toBeVisible()
  const submit = page.getByRole("button", { name: "记录人工判断" })
  await expect(submit).toBeDisabled()
  await page
    .getByLabel("判断理由（至少 10 个字符）")
    .fill("请求输入未转义直接以HTML响应返回")
  const proof = page.getByRole("checkbox", {
    name: "源码 · app.py",
    exact: true,
  })
  await proof.uncheck()
  await expect(submit).toBeDisabled()
  await expect(page.getByText("请选择至少一条源码或查询证据")).toBeVisible()
  await proof.check()
  const request = page.waitForRequest((r) =>
    r.url().includes("/candidates/candidate-1/decisions"),
  )
  await submit.click()
  expect((await request).postDataJSON()).toEqual({
    status: "confirmed",
    reason: "请求输入未转义直接以HTML响应返回",
    evidence_ids: ["evidence-1"],
  })
})
test("切换候选清空理由；提交失败保留输入", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [
      candidate,
      {
        ...candidate,
        id: "candidate-2",
        identity_key: "xss-2",
        title: "第二个待审候选",
      },
    ],
  })
  await page.goto("/audits/task-1?stage=review")
  const reason = page.getByLabel("判断理由（至少 10 个字符）")
  await reason.fill("这是第一条候选的判断理由")
  await page.getByRole("button", { name: /第二个待审候选/ }).click()
  await expect(reason).toHaveValue("")
  await reason.fill("第二个候选的人工判断依据")
  await page.route("**/candidates/candidate-2/decisions", (route) =>
    route.fulfill({ status: 500, json: { detail: "保存失败" } }),
  )
  await page.getByRole("button", { name: "记录人工判断" }).click()
  await expect(
    page.getByRole("alert").filter({ hasText: "保存失败" }).first(),
  ).toBeVisible()
  await expect(reason).toHaveValue("第二个候选的人工判断依据")
})
test("原始未知建议和历史 supported 建议分别显示", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/stages": [
      {
        id: "review-1",
        kind: "review",
        status: "completed",
        phase: "awaiting_human_decisions",
        created_at: "2026-10-11",
        result: {
          batches: [
            {
              assessments: [
                { candidate_id: "candidate-1", assessment: "supported" },
              ],
            },
          ],
        },
      },
    ],
  })
  await page.goto("/audits/task-1?stage=review")
  await expect(page.getByText("原始模型建议：未知（unknown）")).toBeVisible()
  await expect(page.getByText("复核历史建议：supported（建议）")).toBeVisible()
  await expect(page.getByText("待确认", { exact: true }).first()).toBeVisible()
})
