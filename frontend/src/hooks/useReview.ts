import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, getApiErrorMessage } from '../api/client'

// ── Types (mirror backend/app/api/reviews.py) ──────────────────────────────

export interface ReviewItem {
  id: string
  inspection_id: string
  field_type: string
  original_value?: Record<string, unknown>
  original_confidence: number
  status: 'pending' | 'confirmed' | 'corrected'
  assigned_to?: string | null
}

export interface ReviewQueueResponse {
  items: ReviewItem[]
  total: number
  pending_count: number
}

export interface CorrectionRequest {
  corrected_value: Record<string, unknown>
  reason: string
}

export interface ConfirmRequest {
  confirmed_value?: Record<string, unknown>
}

export interface CorrectionResponse {
  correction_id: string
  field_type: string
  original_value?: Record<string, unknown>
  corrected_value: Record<string, unknown>
  reason: string
  corrected_by: string
  compliance_status_after: string
}

// ── Hooks ──────────────────────────────────────────────────────────────────

/** GET /api/v1/reviews/queue — requires senior_officer+ per prd.md §21 */
export function useReviewQueue() {
  return useQuery({
    queryKey: ['reviews', 'queue'],
    queryFn: async () => {
      const { data } = await apiClient.get<ReviewQueueResponse>('/reviews/queue')
      return data
    },
    // 403 from interceptor when role insufficient — poll defer is fine
    retry: false,
  })
}

/** POST /reviews/{id}/confirm — any authenticated user */
export function useConfirmReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { reviewId: string; body: ConfirmRequest }) => {
      const { data } = await apiClient.post(`/reviews/${params.reviewId}/confirm`, params.body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] })
    },
  })
}

/** POST /reviews/{id}/override — senior_officer+ only */
export function useOverrideReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { reviewId: string; body: CorrectionRequest }) => {
      const { data } = await apiClient.post<CorrectionResponse>(
        `/reviews/${params.reviewId}/override`,
        params.body,
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviews', 'queue'] })
    },
  })
}

/** POST /reviews/{id}/override with error message helper */
export function useOverrideReviewWithMessage() {
  const override = useOverrideReview()

  return {
    ...override,
    mutateAsync: async (params: { reviewId: string; body: CorrectionRequest }) => {
      try {
        return await override.mutateAsync(params)
      } catch (err) {
        throw new Error(getApiErrorMessage(err, 'Could not submit correction'))
      }
    },
  }
}
