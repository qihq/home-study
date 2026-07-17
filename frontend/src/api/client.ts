export class ApiError extends Error {
  constructor(public readonly code: string, message: string, public readonly status: number) { super(message) }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type') && typeof init.body === 'string') headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new ApiError(payload?.detail?.code ?? 'REQUEST_FAILED', payload?.detail?.message ?? '请求失败', response.status)
  }
  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('Content-Type') ?? ''
  if (!contentType.includes('application/json')) return undefined as T
  return response.json() as Promise<T>
}

export async function apiAudio(path: string): Promise<Blob> {
  return apiBlob(path)
}

export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type') && typeof init.body === 'string') headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) throw new ApiError('AUDIO_REQUEST_FAILED', '音频请求失败', response.status)
  return response.blob()
}
