import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiClient,
  REFRESH_TOKEN_KEY,
  TOKEN_KEY,
  type LoginResponse,
} from '../api/client'

export interface LoginCredentials {
  email: string
  password: string
}

/**
 * useLogin — POST /auth/login per prd.md §21.
 *
 * On success stores the access + refresh tokens (prd.md §25.2) and
 * invalidates cached queries so the UI reflects the authenticated user.
 */
export function useLogin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (credentials: LoginCredentials): Promise<LoginResponse> => {
      const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials)
      localStorage.setItem(TOKEN_KEY, data.access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries()
    },
  })
}

/** useLogout — clears stored credentials and all cached queries. */
export function useLogout() {
  const queryClient = useQueryClient()

  return () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    queryClient.clear()
  }
}

/** useAuthToken — current access token, if any. */
export function useAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}