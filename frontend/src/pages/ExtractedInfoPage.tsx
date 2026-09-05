import { useParams } from 'react-router-dom'
import { useInspection } from '../hooks/useInspection'
import { ComplianceStatusBadge } from '../components/ComplianceStatusBadge'

const confidenceColor = (c: number) => {
  if (c >= 0.85) return 'text-ink'
  if (c >= 0.6) return 'text-amber-flag-dark'
  return 'text-redline'
}


export function ExtractedInfoPage() {
  const { id } = useParams<{ id: string }>()
  const inspection = useInspection(id)

  if (inspection.isLoading) return <p className="text-ink">Loading declarations…</p>
  if (inspection.isError) return <p className="text-redline">Failed to load declarations</p>

  const data = inspection.data as any
  if (!data) return null

  const declarations = (data as any).declarations ?? []
  const overallStatus = (data as any).overall_status ?? null

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-redline mono tracking-wider uppercase text-sm mb-1">Extracted declarations</p>
          <h1 className="text-2xl font-medium text-ink">Declaration review</h1>
        </div>
        {overallStatus && <ComplianceStatusBadge status={overallStatus} />}
      </header>

      {declarations.length === 0 ? (
        <p className="text-ink/70 italic">No declarations extracted yet.</p>
      ) : (          <ul className="flex flex-col gap-3">
          {declarations.map((decl: any) => {
            const valueText = decl.value?.text ?? 'Not found'
            const confidence = decl.confidence ?? 0
            return (
              <li key={decl.field_type} className="flex flex-col gap-1 border-b border-ink/20 pb-3">
                <p className="text-ink/60 text-xs uppercase tracking-wide">{decl.field_type}</p>
                <p className="text-ink text-lg font-medium">{valueText}</p>
                <p className={`text-xs ${confidenceColor(confidence)}`}>
                  {confidence >= 0.85 ? 'High confidence' : confidence >= 0.6 ? 'Review recommended' : 'Low confidence — verify manually'}
                </p>
              </li>
            )
          })}
        </ul>
      )}

      <footer className="flex justify-end mt-4 border-t border-ink/20 pt-4">
        <a
          href="#"
          className="px-4 py-2 text-sm rounded-full bg-ink text-paper hover:opacity-90"
          style={{ borderRadius: '999px' }}
        >
          Continue to compliance
        </a>
      </footer>
    </div>
  )
}
