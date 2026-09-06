import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

// ── Types (mirror backend/app/api/rules.py + backend/app/schemas/rule.py) ──

export interface RuleSummary {
  id: string
  rule_key: string
  title: string
  version: number
  latest_version_id: string
  effective_date: string
  product_categories: string[]
  severity: string
}

export interface RuleListResponse {
  rules: RuleSummary[]
}

export interface RuleVersion {
  id: string
  version: number
  content: Record<string, unknown>
  legal_reference: string
  effective_date: string
  end_date?: string | null
  published_by?: string | null
  published_at?: string | null
  is_published: boolean
}

export interface RuleDetail {
  id: string
  rule_key: string
  title: string
  description?: string | null
  versions: RuleVersion[]
  current_version_id?: string | null
  current_effective_date?: string | null
}

export interface RuleCreateRequest {
  rule_key: string
  title: string
  description?: string
  product_categories: string[]
  package_type?: string
  severity: string
}

export interface RuleVersionCreateRequest {
  content: Record<string, unknown>
  legal_reference: string
  effective_date: string
  end_date?: string
}

export interface RuleVersionResponse {
  id: string
  version: number
  content: Record<string, unknown>
  legal_reference: string
  effective_date: string
  message: string
}

export interface RulePublishRequest {
  published_by: string
}

// ── Hooks ──────────────────────────────────────────────────────────────────

/** GET /api/v1/rules — admin/senior_officer per prd.md §21 */
export function useRules(params?: Record<string, string | number | boolean>) {
  return useQuery({
    queryKey: ['rules', params],
    queryFn: async () => {
      const { data } = await apiClient.get<RuleListResponse>('/rules', { params })
      return data
    },
    // 403 when not authorized — render empty list state
    retry: false,
  })
}

/** POST /rules — admin only */
export function useCreateRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (body: RuleCreateRequest) => {
      const { data } = await apiClient.post<RuleVersionResponse>('/rules', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

/** GET /rules/{ruleId} — admin/senior_officer */
export function useRuleDetail(ruleId: string | undefined) {
  return useQuery({
    queryKey: ['rules', ruleId],
    enabled: Boolean(ruleId),
    queryFn: async () => {
      const { data } = await apiClient.get<RuleDetail>(`/rules/${ruleId}`)
      return data
    },
    retry: false,
  })
}

/** POST /rules/{ruleId}/versions — admin only */
export function useAddRuleVersion() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { ruleId: string; body: RuleVersionCreateRequest }) => {
      const { data } = await apiClient.post<RuleVersionResponse>(
        `/rules/${params.ruleId}/versions`,
        params.body,
      )
      return data
    },
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['rules', vars.ruleId] })
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

/** POST /rules/{ruleId}/versions/{versionId}/publish — admin only */
export function usePublishRuleVersion() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { ruleId: string; versionId: string; body: RulePublishRequest }) => {
      const { data } = await apiClient.post<{ version: RuleVersionResponse; message: string }>(
        `/rules/${params.ruleId}/versions/${params.versionId}/publish`,
        params.body,
      )
      return data
    },
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['rules', vars.ruleId] })
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}
