import { apiJson, downloadArtifact } from "./backend"
export interface CodeLocation {
  file: string
  line: number
  column: number
  end_line: number
}
export interface Finding {
  id: string
  rule: string
  message: string
  level: string
  security_severity: string | null
  locations: CodeLocation[]
  code_flows: CodeLocation[][]
  assessment: string
}
export interface AuditRun {
  id: string
  project_name: string
  language: string
  status: string
  phase: string
  snapshot_hash: string
  query_pack: string
  suite: string
  codeql_version: string | null
  error: string | null
  coverage: {
    files_by_language?: Record<string, number>
    unscanned_languages?: string[]
    pipeline_version?: string
    dual_engine?: {
      status: string
      review_ready?: boolean
      codeql?: { status: string; error?: string }
      scout?: {
        status: string
        error?: string
        coverage?: {
          status: string
          planned_windows: number
          inspected_windows: number
          uninspected_windows: number
        }
      }
    }
  }
  custom_rule_ids: string[]
  findings: Finding[]
  created_at: string
}
export interface Environment {
  codeql_version: string | null
  error: string | null
  query_packs_present: boolean
  queue_available: boolean
}
export interface SourceExcerpt {
  file: string
  start_line: number
  lines: string[]
}

const request = <T>(path: string, options?: RequestInit) =>
  apiJson<T>(`/audits${path}`, options)
export const getRuns = () => request<AuditRun[]>("/")
export const getEnvironment = () => request<Environment>("/environment")
export const getLogs = (id: string) => request<{ text: string }>(`/${id}/logs`)
export const getSource = (id: string, location: CodeLocation) =>
  request<SourceExcerpt>(
    `/${id}/source?${new URLSearchParams({ file: location.file, line: String(Math.max(location.line, 1)) })}`,
  )
export const retryRun = (id: string) =>
  request<AuditRun>(`/${id}/retry`, { method: "POST" })
export const cancelRun = (id: string) =>
  request<AuditRun>(`/${id}/cancel`, { method: "POST" })
export const recoverRun = (id: string) =>
  request<AuditRun>(`/${id}/recover`, { method: "POST" })
export function uploadRun(
  file: File,
  name: string,
  language: string,
  ruleIds: string[] = [],
) {
  const body = new FormData()
  body.append("file", file)
  body.append("project_name", name)
  body.append("language", language)
  body.append("rule_ids", ruleIds.join(","))
  return request<AuditRun>("/", { method: "POST", body })
}
export const downloadSarif = (id: string) =>
  downloadArtifact(`/audits/${id}/sarif`, `${id}.sarif`)
