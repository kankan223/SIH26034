import type { ReactNode } from 'react'

export type LedgerRowStatus = 'compliant' | 'violation' | 'needs-review' | 'neutral'

const TICK_CLASS: Record<LedgerRowStatus, string> = {
  compliant: 'border-l-verify',
  violation: 'border-l-redline',
  'needs-review': 'border-l-amber',
  neutral: 'border-l-transparent',
}

interface LedgerRowProps {
  /** Status drives the 4px left-edge tick color per design.md §3.2. */
  status?: LedgerRowStatus
  /** Left-side label shown before children (e.g. field type name) */
  leftLabel?: string
  /** Right-side label shown after children (e.g. confidence score) */
  rightLabel?: string
  /** Right-side link rendered after rightLabel, if any */
  rightLink?: ReactNode
  children: ReactNode
  onClick?: () => void
  className?: string
}

/**
 * LedgerRow — the Docket primary content pattern (design.md §3.2).
 *
 * A full-width horizontal record separated from its neighbors by a 1px
 * hairline, with a 4px left-edge status tick. Replaces rounded cards
 * everywhere except evidence cards and KPI figure blocks.
 */
export function LedgerRow({
  status = 'neutral',
  leftLabel,
  rightLabel,
  rightLink,
  children,
  onClick,
  className = '',
}: LedgerRowProps) {
  const base =
    'flex w-full items-center justify-between gap-4 border-b border-ink/10 border-l-4 ' +
    `py-2 pl-3 pr-2 text-left ${TICK_CLASS[status]} ${className}`

  const leftContent = leftLabel ? (
    <span className="text-micro text-ink/50">{leftLabel}</span>
  ) : null
  const rightContent = (
    <span className="flex items-center gap-2">
      {rightLabel && <span className="text-micro text-ink/50">{rightLabel}</span>}
      {rightLink}
    </span>
  )

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={base}>
        {leftContent}
        {children}
        {rightContent}
      </button>
    )
  }

  return (
    <div className={base}>
      {leftContent}
      {children}
      {rightContent}
    </div>
  )
}

export default LedgerRow