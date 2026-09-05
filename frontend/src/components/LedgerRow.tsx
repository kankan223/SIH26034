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
  children,
  onClick,
  className = '',
}: LedgerRowProps) {
  const base =
    'flex w-full items-center justify-between gap-4 border-b border-ink/10 border-l-4 ' +
    `py-2 pl-3 pr-2 text-left ${TICK_CLASS[status]} ${className}`

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={base}>
        {children}
      </button>
    )
  }

  return <div className={base}>{children}</div>
}

export default LedgerRow