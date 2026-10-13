import { apiJson } from "./backend"
import type { Evidence } from "./stages"

export interface ReviewDetail {
  title: string
  description: string
  impact: string
  evidence_ids: string[]
  exploitation: {
    status: "illustrative" | "blocked" | "missing_preconditions"
    entrypoint: string
    prerequisites: string[]
    steps: string[]
    example: string
    expected_result: string
    source_quote: string
    evidence_ids: string[]
    execution_status: "not_executed"
  }
}
export interface CandidateReview {
  stage_id: string
  stage_status: string
  status: string
  evaluated: boolean
  reason: string
  checked_premises: string[]
  missing_premises: string[]
  runtime_unknowns: string[]
  detail: ReviewDetail | null
  evidence_ids: string[]
  snapshot_hash: string
  updated_at: string
}
export const getCandidateEvidence = (id: string) =>
  apiJson<Evidence[]>(`/candidates/${id}/evidence`)
export const classifyCandidate = (id: string, status: string) =>
  apiJson(`/candidates/${id}/classification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  })
export const localizeCandidates = (id: string) =>
  apiJson<{ status: string; error?: string | null }>(
    `/audits/${id}/localize-candidates`,
    { method: "POST" },
  )
export const addCandidateSource = (id: string, file: string, line: number) =>
  apiJson<Evidence>(`/candidates/${id}/source`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file, line }),
  })
