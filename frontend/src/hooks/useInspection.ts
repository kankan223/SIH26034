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

// Detail envelope matches backend inspection endpoint + compliance shape
// (backend/app/services/compliance_engine.py — ComplianceResult / ViolationRecord)

export interface InspectionDetail extends Inspection {
  overall_status?: 'COMPLIANT' | 'NON_COMPLIANT' | 'PARTIALLY_COMPLIANT' | 'NEEDS_HUMAN_REVIEW' | 'INSUFFICIENT_EVIDENCE'
  status_reason?: string
  compliance?: {
    per_field_compliance?: Array<{
      field_type: string
      status: string
      rule_version_id: string
      confidence: number
      detail: string
    }>
    violations?: Array<{
      field: string
      severity: 'critical' | 'major' | 'minor'
      rule_version_id: string
      rule_key: string
      issue_description: string
      expected_condition?: string
    }>
  }
}

// Dashboard response shapes mirror backend/app/schemas/dashboard.py (prd.md §23)

export interface KpiObject {
  total_inspections: number
  compliant_count: number
  non_compliant_count: number
  flagged_for_review_count: number
  pending_review_count: number
  active_violations_count: number
  compliance_rate_percent: number
  total_products_categorized: number
  top_category: string | null
}

export interface TrendPoint {
  month: string
  inspection_count: number
  compliant_count: number
  compliance_rate_percent: number
}

export interface TrendResponse {
  trends: TrendPoint[]
  total_months: number
}

export interface CategoryViolation {
  category: string
  violation_count: number
  compliance_rate_percent: number
}

export interface CategoryResponse {
  categories: CategoryViolation[]
  total_violations: number
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
      const { data } = await apiClient.get<InspectionDetail>(`/inspections/${id}`)
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
      const { data } = await apiClient.get<KpiObject>('/dashboard/kpis')
      return data
    },
  })
}

/** useDashboardTrends — GET /dashboard/trends (admin per prd.md §21). */
export function useDashboardTrends() {
  return useQuery({
    queryKey: ['dashboard', 'trends'],
    queryFn: async () => {
      const { data } = await apiClient.get<TrendResponse>('/dashboard/trends')
      return data
    },
    retry: false,
  })
}

/** useDashboardCategories — GET /dashboard/categories (admin per prd.md §21). */
export function useDashboardCategories() {
  return useQuery({
    queryKey: ['dashboard', 'categories'],
    queryFn: async () => {
      const { data } = await apiClient.get<CategoryResponse>('/dashboard/categories')
      return data
    },
    retry: false,
  })
}
