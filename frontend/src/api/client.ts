import axios from 'axios'

// JWT is held in memory only (todo.md Task 8.2.1 verification #5) —
// never persisted to localStorage — to limit XSS exposure.
let accessToken: string | null = null
let refreshToken: string | null = null

export function setAuthTokens(access: string, refresh: string): void {
  accessToken = access
  refreshToken = refresh
}

export function getAuthToken(): string | null {
  return accessToken
}

export function getRefreshToken(): string | null {
  return refreshToken
}

export function clearAuthTokens(): void {
  accessToken = null
  refreshToken = null
}

export interface DocketUser {
  id: string
  email: string
  role: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: DocketUser
}

/**
 * Shared Axios client for the Docket backend.
 *
 * baseURL defaults to `/api/v1` (proxied by the Vite dev server to the
 * FastAPI backend on :8000); override with VITE_API_BASE_URL in prod.
 * A request interceptor attaches the in-memory JWT as a Bearer token,
 * and a response interceptor clears credentials + redirects to /login
 * on 401.
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAuthTokens()
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

/** Extract a human-readable message from an API error (FastAPI `detail`). */
export function getApiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (typeof detail === 'string' && detail.length > 0) return detail
  }
  return error instanceof Error && error.message ? error.message : fallback
}

export default apiClient