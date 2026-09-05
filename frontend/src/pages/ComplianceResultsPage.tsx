import { useParams } from 'react-router-dom'
import { useInspection } from '../hooks/useInspection'
import { ComplianceStatusBadge } from '../components/ComplianceStatusBadge'
import { EvidenceCard } from '../components/EvidenceCard'
import { MeasureRule } from '../components/MeasureRule'

const verdictTick = (status: string) => {
  if (status === 'PASS') return 'pass'
  if (status === 'FAIL') return 'fail'
  return 'review'
}

export function ComplianceResultsPage() {
  const { id } = useParams<{ id: string }>()
  const inspection = useInspection(id)

  if (inspection.isLoading) return <p className="text-ink">Computing compliance…</p>
  if (inspection.isError) return <p className="text-redline">Failed to evaluate compliance</p>

  const data = inspection.data as any
  if (!data) return null

  const status = data.overall_status ?? 'UNKNOWN'
  const reason = data.status_reason ?? ''
  const perField = data.compliance?.per_field_compliance ?? []
  const violations = data.compliance?.violations ?? []

  return (
    <article className="flex flex-col gap-6 relative">
      {/* Measure Rule: one tick per rule check, colored by verdict per design.md §6 & §8.6 */}
      <div
        className="hidden lg:flex lg:absolute lg:left-0 lg:top-20 lg:h-[calc(100%-5rem)] lg:justify-center"
        aria-hidden="true"
      >
        <MeasureRule ticks={perField.slice(0, 10).map((fc: any) => ({
          label: fc.field_type,
          state: verdictTick(fc.status),
        }))} />
      </div>

      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-redline mono tracking-wider uppercase text-sm mb-1">Compliance results</p>
          <h1 className="text-2xl font-medium text-ink">Inspection {String(data.id).slice(0, 8)}</h1>
          {reason && <p className="text-ink/80 mt-1">{reason}</p>}
        </div>
        <ComplianceStatusBadge status={status} />
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium text-ink">Rule check results</h2>
        {perField.length === 0 ? (
          <p className="text-ink/70 italic">No rule checks evaluated yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {perField.map((fc: any) => (
              <li key={fc.rule_version_id} className="flex items-start gap-3 border-b border-ink/20 pb-2">
                <span className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                  fc.status === 'PASS'
                    ? 'bg-ink/10 border-ink/40 text-ink'
                    : fc.status === 'FAIL'
                    ? 'bg-redline/10 border-redline text-redline'
                    : 'bg-amber-flag/10 border-amber-flag-dark text-amber-flag-dark'
                }`}>
                  {fc.status === 'PASS' ? '✓' : fc.status === 'FAIL' ? '✗' : '!'}
                </span>
                <div className="flex-1">
                  <p className="font-medium text-ink">{fc.field_type}</p>
                  <p className="text-ink/80 text-sm">{fc.detail}</p>
                  <p className="text-ink/60 text-xs mono mt-1">rule {fc.rule_version_id}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {violations.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-medium text-ink">Violation evidence</h2>
          <ul className="flex flex-col gap-3">
            {violations.map((v: any, _idx: number) => (
              <li key={_idx}>
                <EvidenceCard
                  violationId={`V-${v.rule_version_id}`}
                  detected={v.field}
                  expected={v.expected_condition ?? 'See rule specification'}
                  ruleCitation={`Rule ${v.rule_version_id} · ${v.rule_key}`}
                  imageUrl="/placeholder-evidence.svg"
                  sourceCrop
                />
                <p className="text-redline text-sm">{v.issue_description}</p>
                {v.expected_condition &&
                  (<p className="text-ink/70 text-xs italic">{v.expected_condition}</p>)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="flex justify-end mt-4 border-t border-ink/20 pt-4">
        <a
          href="#"
          className="px-4 py-2 text-sm rounded-full bg-ink text-paper hover:opacity-90"
          style={{ borderRadius: '999px' }}
        >
          Export report
        </a>
      </footer>
    </article>
  )
}
