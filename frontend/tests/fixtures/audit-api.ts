import type { Page } from "@playwright/test"
export const audit = {
  id: "task-1",
  project_name: "flask-get-xss-vulnerable",
  language: "python",
  status: "completed",
  phase: "discovery_ready",
  snapshot_hash: "75127fd2a52abf99",
  query_pack: "codeql/python-queries@1.6.0",
  suite: "security-extended",
  codeql_version: "2.23.5",
  error: null,
  custom_rule_ids: [],
  findings: [],
  created_at: "2026-10-11T08:00:00Z",
  coverage: {
    dual_engine: {
      status: "completed",
      review_ready: true,
      codeql: { status: "completed" },
      scout: { status: "completed" },
    },
  },
}
export const candidate = {
  id: "candidate-1",
  audit_id: "task-1",
  stage_id: "stage-1",
  origin: "ai",
  title: "未转义输入导致反射型 XSS",
  description: "用户输入直接作为 HTML 返回",
  status: "pending",
  evidence_ids: ["evidence-1"],
  static_finding_id: null,
  related_target: null,
  weakness: "CWE-79",
  model_assessment: "unknown",
  novelty: "new",
  identity_key: "xss-1",
  location: { file: "app.py", line: 7 },
}
export const evidence = {
  id: "evidence-1",
  stage_id: "stage-1",
  kind: "code",
  content:
    "from flask import Flask, request\nfrom markupsafe import escape\napp = Flask(__name__)\n\n@app.get('/view')\ndef endpoint():\n    return request.args['payload']",
  reference: { file: "app.py", start_line: 1 },
  snapshot_hash: "75127fd2a52abf99",
  digest: "c28e98793d49c118",
}
export async function mockAuditApi(
  page: Page,
  overrides: Record<string, unknown> = {},
) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "")
    const data: Record<string, unknown> = {
      "/audits/": [audit],
      "/audits/environment": {
        codeql_version: "2.23.5",
        error: null,
        query_packs_present: true,
        queue_available: true,
      },
      "/audits/task-1/stages": [],
      "/audits/task-1/candidates": [candidate],
      "/audits/task-1/evidence": [evidence],
      "/audits/task-1/logs": { text: "" },
      "/audits/task-1/repairs": [],
      "/knowledge/capabilities": {
        model_configured: true,
        model: "configured-model",
        embedding_model: null,
        retrieval: "bm25",
      },
      "/knowledge/": [],
      "/rules/": [],
      "/rules/holdouts": [],
      ...overrides,
    }
    if (data[path] === "ERROR") {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "候选读取失败" }),
      })
      return
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(data[path] ?? []),
    })
  })
}
