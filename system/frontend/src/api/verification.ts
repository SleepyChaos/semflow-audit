import { apiJson } from "./backend"
import type { StageRun } from "./stages"
export interface VerificationCase {
  name: string
  category: "security" | "functional"
  candidate_ids: string[]
  input_description: string
  expected_behavior: string
}
export interface VerificationSuite {
  id: string
  image: string
  suite_hash: string
  snapshot_hash: string
  origin: string
  candidate_ids: string[]
  suite: {
    title: string
    summary: string
    language: string
    files: Record<string, string>
    cases: VerificationCase[]
    assumptions: string[]
  }
}
export interface RepairComparison {
  status: string
  receipt_hash?: string
  stage_id?: string
  summary?: string
  error?: string
  repetitions?: number
  suite_title?: string
  suite_created_before_repair?: boolean
  assumptions?: string[]
  cases?: (VerificationCase & {
    before: string
    after: string
    before_label: string
    after_label: string
    reason: string
  })[]
  runs?: unknown[]
  identity?: {
    suite_id: string
    suite_hash: string
    source_snapshot: string
    patched_snapshot: string
  }
}
const post = <T>(path: string, body: unknown) =>
  apiJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
export const getVerificationSuites = (auditId: string) =>
  apiJson<VerificationSuite[]>(`/audits/${auditId}/verification-suites`)
export const getVerificationEnvironment = (auditId: string) =>
  apiJson<{ ready: boolean; error: string | null }>(
    `/audits/${auditId}/verification-environment`,
  )
export const generateVerificationSuite = (
  auditId: string,
  body: { candidate_ids: string[]; image: string; requirements: string },
) => post<StageRun>(`/audits/${auditId}/verification-suites/generate`, body)
export const importVerificationSuite = (auditId: string, body: unknown) =>
  post<StageRun>(`/audits/${auditId}/verification-suites/import`, body)
export const verifyRepair = (id: string, suiteId: string) =>
  post<StageRun>(`/repairs/${id}/verify`, { suite_id: suiteId })
