export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}
export async function apiFetch(path: string, options?: RequestInit) {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(
      typeof body.detail === "string"
        ? body.detail
        : `请求失败 (${response.status})`,
      response.status,
    )
  }
  return response
}
export async function apiJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  return (await apiFetch(path, options)).json()
}
export async function downloadArtifact(path: string, filename: string) {
  const response = await apiFetch(path)
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
