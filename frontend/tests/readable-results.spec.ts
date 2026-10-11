import { expect, test } from "@playwright/test"
import { candidate, mockAuditApi } from "./fixtures/audit-api"

test("候选先显示问题位置、影响和下一步，原文可展开", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/candidates": [
      {
        ...candidate,
        title: "Reflected XSS",
        explanation: {
          title: "网页输出未正确转义（XSS）",
          location: "app.py:7",
          status: "待人工确认",
          observation: "URL 参数直接作为 HTML 返回，尚需核对响应和防护。",
          source_quote: "return request.args['payload']",
          risk: "输入中的脚本可能在浏览器执行。",
          remediation: "对网页输出做正确转义。",
          next_step: "核对源码，再确认或排除。",
          boundary: "这是候选，不是已确认漏洞。",
        },
      },
    ],
  })
  await page.goto("/audits/task-1?stage=review")
  await expect(
    page.getByText("URL 参数直接作为 HTML 返回，尚需核对响应和防护。", {
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.locator(".reader-explanation").getByText("app.py:7", { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText("核对源码，再确认或排除。", { exact: true }),
  ).toBeVisible()
  await page.getByText("原始模型说明与判断要求", { exact: true }).click()
  await expect(page.getByText("Reflected XSS", { exact: true })).toBeVisible()
})

test("镜像缺失显示环境受阻与下一步，不显示补丁修复成功", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/repairs": [
      {
        id: "repair-1",
        stage_id: "stage-1",
        candidate_ids: [],
        changes: [],
        status: "needs_review",
        acceptance_reason: null,
        validation: {
          environment: { status: "blocked", output: "验证镜像未安装" },
        },
        validation_summary: [
          {
            label: "验证环境",
            status: "环境未就绪",
            description: "验证镜像未安装",
            next_step: "准备镜像后创建新记录；不证明补丁错误。",
          },
        ],
      },
    ],
  })
  await page.goto("/audits/task-1?stage=repair")
  await expect(page.getByText("验证镜像未安装", { exact: true })).toBeVisible()
  await expect(
    page.getByText("准备镜像后创建新记录；不证明补丁错误。", { exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "接受此补丁" })).toHaveCount(0)
})

test("语法通过仍显示功能和漏洞检查未执行", async ({ page }) => {
  await mockAuditApi(page, {
    "/audits/task-1/repairs": [
      {
        id: "repair-1",
        stage_id: "stage-1",
        candidate_ids: [],
        changes: [],
        status: "checks_passed",
        acceptance_reason: null,
        validation: { isolated_tests: { status: "passed", profile: "syntax" } },
        validation_summary: [
          {
            label: "语法检查",
            status: "通过",
            description: "代码可以解析。",
            next_step: "补充功能测试。",
          },
          {
            label: "漏洞验证",
            status: "未执行",
            description: "尚未验证攻击输入。",
            next_step: "比较修复前后。",
          },
        ],
      },
    ],
  })
  await page.goto("/audits/task-1?stage=repair")
  await expect(
    page.getByText("尚未验证攻击输入。", { exact: true }),
  ).toBeVisible()
  await expect(page.getByText("比较修复前后。", { exact: true })).toBeVisible()
})
