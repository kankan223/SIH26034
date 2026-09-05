import { useParams, Link } from 'react-router-dom'
import { useInspection } from '../hooks/useInspection'
import { ComplianceStatusBadge } from '../components/ComplianceStatusBadge'

export function InspectionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const inspection = useInspection(id)

  if (inspection.isLoading) return <p className="text-ink">Loading inspection…</p>
  if (inspection.isError) return <p className="text-redline">Failed to load inspection</p>

  const data = inspection.data
  if (!data) return null

  const status = (data as any).overall_status ?? 'UNKNOWN'
  const reason = (data as any).status_reason ?? ''
  const violations = (data as any).compliance?.violations ?? []

  return (
    <article className="flex flex-col gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-redline mono tracking-wider uppercase text-sm mb-1">Inspection {String((data as any).id).slice(0, 8)}</p>
          <h1 className="text-2xl font-medium text-ink">Inspection detail</h1>
          <p className="text-ink/70 mt-1">{String((data as any).location ?? 'Field inspection')}</p>
        </div>
        <ComplianceStatusBadge status={status as any} />
      </header>

      {reason && (
        <p className="text-ink/80 border-l-2 border-ink/20 pl-4 italic">{reason}</p>
      )}

      <section className="grid grid-cols-1 gap-3">
        <h2 className="text-lg font-medium text-ink">Violations</h2>
        {violations.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {violations.map((v: any) => (
              <li key={v.rule_version_id} className="flex flex-col gap-1 border-l-2 border-redline pl-3 py-1">
                <p className="text-redline font-medium text-sm">{v.issue_description}</p>
                <p className="text-ink/70 text-xs mono">
                  {v.field} · {v.severity} · rule {v.rule_version_id}
                </p>
                {v.expected_condition && (
                  <p className="text-ink/60 text-xs italic">{v.expected_condition}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink/70 italic">No violations recorded for this inspection.</p>
        )}
      </section>

      <footer className="flex justify-end gap-2 mt-4 border-t border-ink/20 pt-4">
        <Link
          to={`/inspections/${id}/extracted`}
          className="px-4 py-2 text-sm rounded-full bg-ink text-paper hover:opacity-90"
          style={{ borderRadius: '999px' }}
        >
          Review extracted declarations
        </Link>
        <Link
          to={`/inspections/${id}/compliance`}
          className="px-4 py-2 text-sm rounded-full bg-paper-deep text-ink border border-ink/20 hover:bg-paper"
        >
          Compliance results
        </Link>
      </footer>
    </article>
  )
}
