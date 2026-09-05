import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiClient,
  clearAuthTokens,
  getAuthToken,
  setAuthTokens,
  type LoginResponse,
} from '../api/client'

export interface LoginCredentials {
  email: string
  password: string
}

/**
 * useLogin — POST /auth/login per prd.md §21.
 *
 * On success stores the access + refresh tokens **in memory** (todo.md
 * Task 8.2.1, verification #5) and invalidates cached queries so the UI
 * reflects the authenticated user.
 */
export function useLogin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (credentials: LoginCredentials): Promise<LoginResponse> => {
      const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials)
      setAuthTokens(data.access_token, data.refresh_token)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries()
    },
  })
}

/** useLogout — clears in-memory credentials and all cached queries. */
export function useLogout() {
  const queryClient = useQueryClient()

  return () => {
    clearAuthTokens()
    queryClient.clear()
  }
}

/** useAuthToken — current in-memory access token, if any. */
export function useAuthToken(): string | null {
  return getAuthToken()
}