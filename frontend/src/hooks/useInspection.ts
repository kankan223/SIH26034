import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

export interface Inspection {
  id: string
  status: string
  [key: string]: unknown
}

export interface InspectionListResponse {
  items: Inspection[]
  total: number
  page: number
  page_size: number
}

/**
 * useInspections — GET /inspections per prd.md §21.
 * Accepts query filters (status, region, date_from, date_to, page).
 */
export function useInspections(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['inspections', params],
    queryFn: async () => {
      const { data } = await apiClient.get<InspectionListResponse>('/inspections', { params })
      return data
    },
  })
}

/** useInspection — GET /inspections/{id} per prd.md §21. */
export function useInspection(id: string | undefined) {
  return useQuery({
    queryKey: ['inspections', id],
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<Inspection>(`/inspections/${id}`)
      return data
    },
  })
}

/** useCreateInspection — POST /inspections per prd.md §21. */
export function useCreateInspection() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const { data } = await apiClient.post<Inspection>('/inspections', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
    },
  })
}

/** useDashboardKpis — GET /dashboard/kpis per prd.md §21, §23. */
export function useDashboardKpis() {
  return useQuery({
    queryKey: ['dashboard', 'kpis'],
    queryFn: async () => {
      const { data } = await apiClient.get('/dashboard/kpis')
      return data
    },
  })
}