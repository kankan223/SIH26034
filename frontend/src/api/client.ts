import axios from 'axios'

export const TOKEN_KEY = 'docket_access_token'
export const REFRESH_TOKEN_KEY = 'docket_refresh_token'

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
 * A request interceptor attaches the stored JWT as a Bearer token, and
 * a response interceptor clears credentials on 401.
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
    return Promise.reject(error)
  },
)

export default apiClient