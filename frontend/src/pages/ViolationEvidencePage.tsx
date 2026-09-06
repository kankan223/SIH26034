import { useParams } from 'react-router-dom'
import { EvidenceCard } from '../components/EvidenceCard'
import { MeasureRule } from '../components/MeasureRule'
import { useInspection } from '../hooks/useInspection'

/** Minimal shape of a violation from the inspection detail response. */
interface ViolationField {
  rule_key?: string
  field?: string
  severity?: string
  issue_description?: string
  expected_condition?: string
}

/** Minimal shape of per-field compliance data. */
interface FieldCompliance {
  field_type?: string
  confidence?: number
}

export function ViolationEvidencePage() {
  const { id } = useParams<{ id: string }>()
  const { data: inspection, isLoading, error } = useInspection(id)

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-ink/50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink/20 border-t-ink" />
        <p className="text-small">Loading evidence…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-ink/50">
        <p className="text-small text-redline font-medium">Could not load evidence</p>
      </div>
    )
  }

  const violations: ViolationField[] = inspection?.compliance?.violations ?? []
  const perField: FieldCompliance[] = inspection?.compliance?.per_field_compliance ?? []

  // Pick the first violation for the evidence card + tick display.
  // design.md §8.7 wireframe shows a single evidence card with bbox overlay.
  const first = violations[0]
  const ruleKey = (first as ViolationField).rule_key ?? 'LM-001'
  const field = (first as ViolationField).field ?? ''
  const severity = (first as ViolationField).severity ?? '—'
  const detected = (first as ViolationField).issue_description ?? undefined
  const expected = (first as ViolationField).expected_condition ?? undefined
  const confidence = (perField.find(
    (f) => (f.field_type ?? '') === ((first as ViolationField).field ?? ''),
  )?.confidence) ?? 0

  return (
    <div className="flex flex-col gap-6">
      {/* Page header — left aligned, ledger style */}
      <div>
        <h1 className="font-serif text-title font-semibold text-ink">
          Violation {ruleKey} — {inspection?.id ?? ''}
        </h1>
        <p className="mt-1 text-small text-ink/60">
          {field} · Severity: {severity}
        </p>
      </div>

      {/* Evidence card — §7.3 */}
      <div className="flex flex-col gap-4">
        <EvidenceCard
          violationId={ruleKey}
          detected={detected}
          expected={expected}
          ruleCitation={`Rule citation — ${ruleKey}`}
          imageUrl={(inspection?.image_url ?? undefined) as string | undefined}
          imageWidth={(inspection?.image_width ?? undefined) as number | undefined}
          imageHeight={(inspection?.image_height ?? undefined) as number | undefined}
          sourceCrop
        />
      </div>

      {/* Rule citation block — serif per design.md §7.3 */}
      <figure className="border-l-4 border-seal pl-4">
        <figcaption className="font-serif text-body-serif leading-relaxed text-ink">
          {ruleKey
            ? `Rule ${ruleKey}, Legal Metrology (Packaged Commodities) Rules, 2011 — the declaration must satisfy the applicable standard for ${field}.`
            : 'Rule citation unavailable.'}
        </figcaption>
      </figure>

      {/* Action buttons — §7.2 verb labels */}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="rounded-control bg-ink text-white px-4 py-2 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          Confirm violation
        </button>
        <button
          type="button"
          className="rounded-control border border-ink bg-transparent px-4 py-2 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          Correct this finding
        </button>
      </div>

      {/* Measure Rule — single tick at confidence position per §6 / §7.5 */}
      <MeasureRule
        tickCount={Math.max(1, Math.round(confidence * 8))}
        ariaLabel="Confidence meter for this evidence field"
      />
    </div>
  )
}

export default ViolationEvidencePage
