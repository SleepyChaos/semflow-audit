export const auditStages = [
  {
    id: "scan",
    title: "审计发现",
    description: "CodeQL 静态分析与 AI 初审的进展、结果和覆盖范围",
  },
  { id: "review", title: "AI 复审", description: "候选、证据与人工判断" },
  {
    id: "report",
    title: "审计报告",
    description: "汇总 AI 复审结论、证据、利用用例与审计边界",
  },
  {
    id: "repair",
    title: "代码修复",
    description: "选择已确认漏洞，生成补丁并验证修复前后的行为",
  },
  { id: "rules", title: "RAG 规则", description: "生成、验证与发布" },
] as const
export type AuditStage = (typeof auditStages)[number]["id"]
export function normalizeStage(value: unknown): AuditStage {
  return auditStages.some((stage) => stage.id === value)
    ? (value as AuditStage)
    : "scan"
}
export const stagePanels: Record<AuditStage, string> = {
  scan: "codeql",
  review: "ai",
  report: "report",
  repair: "repair",
  rules: "rag",
}
export function languageName(language: string) {
  return language === "python" ? "Python" : "JavaScript / TypeScript"
}
