import { useParams } from 'react-router-dom'
import { useInspection } from '../hooks/useInspection'
import { ComplianceStatusBadge } from '../components/ComplianceStatusBadge'

/**
 * ReportPage (design.md §8.9).
 *
 * Read-only report preview shell before PDF export. Shows the inspection
 * identity, overall compliance status banner, and a download/print action row.
 *
 * Nested route: /reports (or /reports/:id) — rendered inside Layout → Outlet.
 * Report rendering/data is handled by Phase 7 (report_generator.py); this page
 * is a UI preview shell per the spec.
 */
export function ReportPage() {
  const { id } = useParams<{ id?: string }>()
  const { data: inspection, isLoading, error } = useInspection(id ?? undefined)

  const status =
    inspection?.overall_status === 'COMPLIANT'
      ? 'compliant'
      : inspection?.overall_status === 'NON_COMPLIANT'
        ? 'violation'
        : inspection?.overall_status === 'NEEDS_HUMAN_REVIEW'
          ? 'review'
          : 'pending'

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-ink/50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink/20 border-t-ink" />
        <p className="text-small">Loading report…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-ink/50">
        <p className="text-small text-redline font-medium">Could not load report</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div>
        <h1 className="font-serif text-title font-semibold text-ink">
          Compliance report
        </h1>
        <p className="mt-1 text-small text-ink/60 font-mono">{inspection?.id ?? '—'}</p>
      </div>

      {/* Status banner — full-width band per §9, colored by overall status */}
      <div
        className={`rounded-surface border border-ink/10 px-6 py-4 text-center ${
          status === 'compliant'
            ? 'bg-verify/10 text-verify'
            : status === 'violation'
              ? 'bg-redline/10 text-redline'
              : status === 'review'
                ? 'bg-amber/10 text-amber-text'
                : 'bg-ink/5 text-ink/60'
        }`}
      >
        <p className="text-label font-medium">
          {status === 'compliant' && 'Compliant — no violations found'}
          {status === 'violation' && 'Non-compliant — violations detected'}
          {status === 'review' && 'Needs human review — findings to verify'}
          {status === 'pending' && 'Pending — analysis not yet complete'}
        </p>
      </div>

      {/* Report metadata — ledger style */}
      <dl className="grid grid-cols-2 gap-4 border-t border-ink/10 pt-4">
        <div className="flex flex-col gap-1">
          <dt className="text-micro text-ink/50">Inspection ID</dt>
          <dd className="font-mono text-small text-ink">{inspection?.id ?? '—'}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-micro text-ink/50">Status</dt>
          <dd className="flex items-center gap-2">
            <ComplianceStatusBadge status={status === 'review' || status === 'pending' ? ('needs-review' as const) : (status as 'compliant' | 'violation')} />
          </dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-micro text-ink/50">Generated</dt>
          <dd className="text-small text-ink">{new Date().toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-micro text-ink/50">Product</dt>
          <dd className="text-small text-ink">{inspection?.product_name ?? '—'}</dd>
        </div>
      </dl>

      {/* Preview note — this is a screen preview, the PDF is generated separately */}
      <div className="border border-ink/20 rounded-surface bg-paper-deep px-4 py-4">
        <p className="text-small text-ink/70">
          This is a screen preview. Use the actions below to download the full PDF report or
          print the current page.
        </p>
      </div>

      {/* Action buttons — §7.2 verb labels */}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="rounded-control bg-ink text-white px-4 py-2 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink flex items-center gap-2"
        >
          Download PDF
        </button>
        <button
          type="button"
          className="rounded-control border border-ink bg-transparent px-4 py-2 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink flex items-center gap-2"
        >
          Print report
        </button>
        <button
          type="button"
          className="rounded-control border border-ink bg-transparent px-4 py-2 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink flex items-center gap-2"
        >
          Regenerate
        </button>
      </div>

      {/* Placeholder for report content (detail rendered by Phase 7 backend) */}
      <section className="border-t border-ink/10 pt-6">
        <h2 className="mb-3 text-section font-medium text-ink">Declarations</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {inspection?.compliance?.per_field_compliance?.map((field) => (
            <div key={field.field_type} className="flex items-center justify-between border-b border-ink/10 pb-2">
              <span className="text-body text-ink">{field.field_type}</span>
              <span className="text-label font-medium">
                {field.status === 'PASS'
                  ? 'Pass'
                  : field.status === 'FAIL'
                    ? 'Fail'
                    : field.status === 'UNABLE_TO_VERIFY'
                      ? 'Unable to verify'
                      : field.status}
              </span>
            </div>
          )) ?? (
            <p className="text-small text-ink/50">No declaration data available.</p>
          )}
        </div>
      </section>
    </div>
  )
}

export default ReportPage
