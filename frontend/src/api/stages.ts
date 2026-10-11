import { apiJson, downloadArtifact } from "./backend"
export interface StageRun {
  id: string
  audit_id: string
  kind: string
  status: string
  phase: string
  inputs: Record<string, unknown>
  result: Record<string, unknown>
  error: string | null
  model: string | null
  model_config_snapshot: Record<string, unknown>
  model_calls: Record<string, unknown>[]
  usage: Record<string, number>
  created_at: string
}
export interface Candidate {
  id: string
  audit_id: string
  stage_id: string
  origin: string
  title: string
  description: string
  status: string
  evidence_ids: string[]
  static_finding_id: string | null
  related_target: string | null
  weakness: string
  model_assessment: string
  novelty: string
  identity_key: string
  location: { file?: string; line?: number }
}
export interface Evidence {
  id: string
  stage_id: string
  kind: string
  content: string
  reference: Record<string, unknown>
  snapshot_hash: string
  digest: string
}
export interface RepairRecord {
  id: string
  stage_id: string
  candidate_ids: string[]
  changes: {
    file: string
    old_text: string
    new_text: string
    reason: string
  }[]
  validation: Record<string, unknown>
  status: string
  acceptance_reason: string | null
}
export interface RuleVersion {
  id: string
  audit_id: string
  stage_id: string
  title: string
  language: string
  purpose: string
  holdout_id: string | null
  strategy: string
  query: string
  modules: Record<string, string>
  query_hash: string
  status: string
  fixtures_approved: boolean
  fixtures: Record<string, unknown>
  validation: Record<string, unknown>
  retrieval: {
    id: string
    title: string
    content: string
    source: string
    version: string
  }[]
}
export interface KnowledgeDocument {
  provenance?: { api_version?: string; license?: string; trust?: string }
  document_id: string
  title: string
  source: string
  language: string
  version: string
  chunks: number
  indexed_chunks: number
  shared: boolean
  index_error: string | null
  corpus: string
}
export interface Capabilities {
  model_configured: boolean
  model: string | null
  embedding_model: string | null
  retrieval: string
}
const post = <T>(path: string, body?: unknown) =>
  apiJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
export const getStages = (auditId: string) =>
  apiJson<StageRun[]>(`/audits/${auditId}/stages`)
export const getCandidates = (auditId: string) =>
  apiJson<Candidate[]>(`/audits/${auditId}/candidates`)
export const getEvidence = (auditId: string) =>
  apiJson<Evidence[]>(`/audits/${auditId}/evidence`)
export const getCapabilities = () =>
  apiJson<Capabilities>("/knowledge/capabilities")
export const startStage = (auditId: string, kind: string, body: unknown) =>
  post<StageRun>(`/audits/${auditId}/${kind}`, body)
export const retryStage = (id: string) => post<StageRun>(`/stages/${id}/retry`)
export const cancelStage = (id: string) => post(`/stages/${id}/cancel`)
export const recoverStage = (id: string) => post(`/stages/${id}/recover`)
export const getStageLogs = (id: string) =>
  apiJson<{ text: string }>(`/stages/${id}/logs`)
export const decideCandidate = (id: string, body: unknown) =>
  post(`/candidates/${id}/decisions`, body)
export const getDecisions = (id: string) =>
  apiJson<Record<string, unknown>[]>(`/candidates/${id}/decisions`)
export const addEvidence = (auditId: string, file: string, line: number) =>
  post(
    `/audits/${auditId}/evidence?${new URLSearchParams({ file, start_line: String(Math.max(1, line - 5)), end_line: String(line + 10) })}`,
  )
export const getRepairs = (auditId: string) =>
  apiJson<RepairRecord[]>(`/audits/${auditId}/repairs`)
export const acceptRepair = (id: string, reason: string) =>
  post(`/repairs/${id}/accept`, { reason })
export const getRules = (language?: string, published = false) =>
  apiJson<RuleVersion[]>(
    `/rules/?${new URLSearchParams({ ...(language ? { language } : {}), published: String(published) })}`,
  )
export const approveFixtures = (id: string, reason: string) =>
  post(`/rules/${id}/approve-fixtures`, { reason })
export const publishRule = (id: string) => post(`/rules/${id}/publish`)
export const retireRule = (id: string) => post(`/rules/${id}/retire`)
export const getKnowledge = () => apiJson<KnowledgeDocument[]>("/knowledge/")
export const importKnowledge = (body: unknown) => post("/knowledge/", body)
export const indexKnowledge = (id: string) => post(`/knowledge/${id}/index`)
export const downloadDiff = (id: string) =>
  downloadArtifact(`/repairs/${id}/diff`, `${id}.diff`)
export const downloadReport = (id: string) =>
  downloadArtifact(`/audits/${id}/report.md`, `${id}-report.md`)
export const downloadReportJson = (id: string) =>
  downloadArtifact(`/audits/${id}/report`, `${id}-report.json`)
export const downloadQuery = (id: string) =>
  downloadArtifact(`/rules/${id}/query`, `${id}.ql`)

export interface RuleHoldout {
  id: string
  language: string
  purpose: string
  operation: string
  hash: string
}
export const getRuleHoldouts = () => apiJson<RuleHoldout[]>("/rules/holdouts")
export const confirmProjectMatch = (
  id: string,
  findingId: string,
  reason: string,
  baselineExclusionReason?: string,
) =>
  post<RuleVersion>(`/rules/${id}/confirm-project-match`, {
    finding_id: findingId,
    reason,
    baseline_exclusion_reason: baselineExclusionReason,
  })
