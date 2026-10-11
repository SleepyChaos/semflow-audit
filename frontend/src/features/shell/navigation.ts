export const auditStages = [
 { id: "scan", title: "CodeQL 审计", description: "扫描结果与覆盖范围" },
 { id: "review", title: "AI 复审", description: "候选、证据与人工判断" },
 { id: "repair", title: "修复与报告", description: "隔离修复与结果导出" },
 { id: "rules", title: "RAG 规则", description: "生成、验证与发布" },
] as const
export type AuditStage = (typeof auditStages)[number]["id"]
export function normalizeStage(value: unknown): AuditStage {
 return auditStages.some(stage => stage.id === value) ? value as AuditStage : "scan"
}
export const stagePanels: Record<AuditStage,string> = {scan:"codeql",review:"ai",repair:"repair",rules:"rag"}
export function languageName(language: string) {
 return language === "python" ? "Python" : "JavaScript / TypeScript"
}
