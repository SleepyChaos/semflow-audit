export async function apiFetch(path: string, options?: RequestInit) {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
      ...options?.headers,
    },
  })
  if ([401, 403].includes(response.status)) {
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
