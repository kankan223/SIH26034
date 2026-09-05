interface BBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

interface EvidenceCardProps {
  /** Violation identifier, rendered in IBM Plex Mono per design.md §7.3. */
  violationId: string
  /** Detected value on the package (Plex Sans). */
  detected?: string
  /** Expected value per the applicable rule. */
  expected?: string
  /** Rule citation, rendered in Source Serif 4 per design.md §7.3. */
  ruleCitation?: string
  /** Evidence crop image URL. */
  imageUrl?: string
  /** Bounding box in pixels; normalised using imageWidth/imageHeight. */
  bbox?: BBox
  /** When true, renders the card framed as a source crop exhibit (border-left drawn in redline). */
  sourceCrop?: boolean
  imageWidth?: number
  imageHeight?: number
}

/**
 * EvidenceCard (design.md §7.3).
 *
 * The one place a bounded surface earns its keep: an image crop framed
 * by a 1px Ink Navy border (0px radius), with the Redline bounding box
 * drawing itself onto the flaw via a 320ms stroke-draw (design.md §5).
 */
export function EvidenceCard({
  violationId,
  detected,
  expected,
  ruleCitation,
  imageUrl,
  bbox,
  sourceCrop,
  imageWidth,
  imageHeight,
}: EvidenceCardProps) {
  const figureClasses = sourceCrop
    ? 'w-full overflow-hidden border-l-2 border-redline pl-0'
    : 'w-full overflow-hidden border border-ink/20'

  // Normalise pixel bbox to a 0–100 viewBox; without dimensions treat
  // the bbox as already-normalised percentages.
  const norm = (value: number, dimension?: number) =>
    dimension ? (value / dimension) * 100 : value

  const bboxPct = bbox
    ? {
        x1: norm(bbox.x1, imageWidth),
        y1: norm(bbox.y1, imageHeight),
        x2: norm(bbox.x2, imageWidth),
        y2: norm(bbox.y2, imageHeight),
      }
    : null

  return (      <figure className={figureClasses} style={{ borderRadius: 0 }}>
      <div className="relative aspect-[4/3] w-full bg-paper-deep">
        {imageUrl ? (
          <img src={imageUrl} alt={`Evidence crop for ${violationId}`} className="h-full w-full object-contain" />
        ) : (
          <div className="flex h-full items-center justify-center text-label text-ink/40">
            No evidence image
          </div>
        )}
        {bboxPct && (
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <rect
              className="bbox-draw"
              x={bboxPct.x1}
              y={bboxPct.y1}
              width={bboxPct.x2 - bboxPct.x1}
              height={bboxPct.y2 - bboxPct.y1}
              fill="var(--color-redline)"
              fillOpacity={0.08}
              stroke="var(--color-redline)"
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        )}
      </div>
      <figcaption className="space-y-1 border-t border-ink/20 p-3">
        <p className="font-mono text-micro text-ink">{violationId}</p>
        {detected !== undefined && (
          <p className="text-small">
            <span className="text-ink/50">Detected:</span> {detected}
          </p>
        )}
        {expected !== undefined && (
          <p className="text-small">
            <span className="text-ink/50">Expected:</span> {expected}
          </p>
        )}
        {ruleCitation !== undefined && (
          <p className="font-serif text-small font-semibold text-ink">{ruleCitation}</p>
        )}
      </figcaption>
    </figure>
  )
}

export default EvidenceCard