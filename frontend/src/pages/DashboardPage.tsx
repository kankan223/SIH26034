import type { ReactNode } from 'react'
import { ComplianceStatusBadge, type ComplianceStatus } from '../components/ComplianceStatusBadge'
import { LedgerRow } from '../components/LedgerRow'
import { MeasureRule, type RuleTick } from '../components/MeasureRule'
import {
  useDashboardCategories,
  useDashboardKpis,
  useDashboardTrends,
  useInspections,
} from '../hooks/useInspection'

function KpiFigure({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="border border-ink/20 bg-paper p-4">
      <p className="font-serif text-display text-ink">{value}</p>
      <p className="text-label text-ink/60">{label}</p>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-2 border-b border-ink/10 pb-1 text-section text-ink">{title}</h2>
      {children}
    </section>
  )
}

/** Map an inspection status string to a badge variant (design.md §7.1). */
function inspectionStatusToBadge(status: string | undefined): ComplianceStatus | null {
  switch (status) {
    case 'COMPLIANT':
      return 'compliant'
    case 'NON_COMPLIANT':
    case 'PARTIALLY_COMPLIANT':
      return 'violation'
    case 'NEEDS_HUMAN_REVIEW':
    case 'FLAGGED_FOR_REVIEW':
    case 'INSUFFICIENT_EVIDENCE':
      return 'needs-review'
    default:
      return null
  }
}

/**
 * DashboardPage (design.md §8.2).
 *
 * Four bounded KPI figure blocks (the one place cards are permitted
 * besides evidence cards), violation categories, and the recent
 * inspections ledger. All data comes from the Phase 7 dashboard APIs.
 */
export function DashboardPage() {
  const kpis = useDashboardKpis()
  const trends = useDashboardTrends()
  const categories = useDashboardCategories()
  const inspections = useInspections({ page_size: 5 })

  const k = kpis.data
  const items = inspections.data?.items ?? []

  // Ticks for the Measure Rule, colored by the verdicts of recent rows.
  const ruleTicks: RuleTick[] = items
    .map((inspection) => inspectionStatusToBadge(inspection.status))
    .filter((badge): badge is ComplianceStatus => badge !== null)
    .map((badge): RuleTick =>
      badge === 'compliant' ? 'pass' : badge === 'violation' ? 'fail' : 'review',
    )

  return (
    <div className="flex gap-6">
      <MeasureRule ticks={ruleTicks} className="w-6 shrink-0 pt-10" />

      <div className="min-w-0 flex-1">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-serif text-title text-ink">Dashboard</h1>
          <div className="flex gap-2 text-small">
            <span className="rounded-[4px] border border-ink/20 px-2 py-1">Region: All ▾</span>
            <span className="rounded-[4px] border border-ink/20 px-2 py-1">This week ▾</span>
          </div>
        </div>

        {kpis.isLoading ? (
          <p className="text-small text-ink/50">Loading KPIs…</p>
        ) : kpis.isError || !k ? (
          <p className="text-small text-redline">Could not load dashboard KPIs.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <KpiFigure label="Inspected" value={k.total_inspections} />
              <KpiFigure label="Compliance rate" value={`${k.compliance_rate_percent}%`} />
              <KpiFigure label="Violations" value={k.active_violations_count} />
              <KpiFigure label="Review queue" value={k.pending_review_count} />
            </div>

            <Section title="Violation categories">
              {categories.isError ? (
                <p className="text-small text-ink/50">
                  Category breakdown requires senior officer access.
                </p>
              ) : categories.isLoading ? (
                <p className="text-small text-ink/50">Loading categories…</p>
              ) : (
                (categories.data?.categories ?? []).map((category) => (
                  <LedgerRow key={category.category} status="violation">
                    <span>{category.category}</span>
                    <span className="text-small text-ink/60">
                      {category.violation_count} violations · {category.compliance_rate_percent}% compliant
                    </span>
                  </LedgerRow>
                ))
              )}
            </Section>

            <Section title="Trends">
              {trends.isError ? (
                <p className="text-small text-ink/50">Trend analytics requires admin access.</p>
              ) : (
                <p className="text-small text-ink/70">
                  {trends.data?.total_months ?? 0} months of data · latest{' '}
                  {trends.data?.trends?.[trends.data.trends.length - 1]?.compliance_rate_percent ?? '—'}%
                  compliance
                </p>
              )}
            </Section>
          </>
        )}

        <Section title="Recent inspections">
          {inspections.isLoading ? (
            <p className="text-small text-ink/50">Loading inspections…</p>
          ) : items.length === 0 ? (
            <p className="text-small text-ink/50">No inspections recorded yet.</p>
          ) : (
            items.map((inspection) => {
              const badge = inspectionStatusToBadge(inspection.status)
              return (
                <LedgerRow key={inspection.id} status={badge ?? 'neutral'}>
                  <span>{String(inspection.product_name ?? inspection.id)}</span>
                  {badge ? (
                    <ComplianceStatusBadge status={badge} />
                  ) : (
                    <span className="text-micro text-ink/50">{String(inspection.status)}</span>
                  )}
                </LedgerRow>
              )
            })
          )}
        </Section>
      </div>
    </div>
  )
}

export default DashboardPage