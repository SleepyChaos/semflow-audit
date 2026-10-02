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
  }
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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/audits${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
      ...options?.headers,
    },
  })
  if (response.status === 401 || response.status === 403) {
    localStorage.removeItem("access_token")
    window.location.assign("/login")
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `请求失败 (${response.status})`,
    )
  }
  return response.json() as Promise<T>
}
export const getRuns = () => request<AuditRun[]>("/")
export const getEnvironment = () => request<Environment>("/environment")
export const getLogs = (id: string) => request<{ text: string }>(`/${id}/logs`)
export const getSource = (id: string, location: CodeLocation) =>
  request<SourceExcerpt>(
    `/${id}/source?${new URLSearchParams({ file: location.file, line: String(Math.max(location.line, 1)) })}`,
  )
export const retryRun = (id: string) =>
  request<AuditRun>(`/${id}/retry`, { method: "POST" })
export function uploadRun(file: File, name: string, language: string) {
  const body = new FormData()
  body.append("file", file)
  body.append("project_name", name)
  body.append("language", language)
  return request<AuditRun>("/", { method: "POST", body })
}
export async function downloadSarif(id: string) {
  const response = await fetch(`/api/v1/audits/${id}/sarif`, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
    },
  })
  if (!response.ok) throw new Error("下载失败，请刷新任务状态后重试")
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `${id}.sarif`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
