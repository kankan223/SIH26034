export function ProcessingScreenPage() {
  const stages = [
    { label: 'Quality gate', state: 'done' },
    { label: 'Package detection', state: 'done' },
    { label: 'OCR', state: 'done' },
    { label: 'Extraction', state: 'processing' },
    { label: 'Classification', state: 'awaiting' },
    { label: 'Rule evaluation', state: 'awaiting' },
  ]

  return (
    <div className="flex flex-col gap-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-redline mono tracking-wider uppercase text-sm mb-1">Inspection processing</p>
          <h1 className="text-2xl font-medium text-ink">Analysis in progress</h1>
        </div>
      </header>

      <ol className="flex flex-col gap-5 pl-6" aria-label="Pipeline stages">
        {stages.map((stage, i) => (
          <li key={i} className="flex gap-4">
            {stage.state === 'done' && (
              <span className="mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-ink text-paper text-sm font-medium">
                ✓
              </span>
            )}
            {stage.state === 'processing' && (
              <span className="mt-1 flex h-6 w-6 animate-pulse rounded-full bg-amber-flag-dark text-paper text-sm font-medium">
                ●
              </span>
            )}
            {stage.state === 'awaiting' && (
              <span className="mt-1 flex h-6 w-6 items-center justify-center rounded-full border-2 border-ink/30 text-ink/40 text-sm font-medium">
                <span className="sr-only">pending</span>
              </span>
            )}
            <span className="text-ink flex-1">{stage.label}</span>
            {stage.state !== 'awaiting' && (
              <span className="text-ink/60 text-xs">completed</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
