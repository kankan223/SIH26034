import type { ReactNode } from 'react'

export type RuleTick = 'pass' | 'fail' | 'review'

const TICK_COLOR: Record<RuleTick, string> = {
  pass: 'bg-verify',
  fail: 'bg-redline',
  review: 'bg-amber',
}

interface MeasureRuleProps {
  /**
   * Ticks rendered top-to-bottom at 24px rhythm, colored by verdict
   * (Teal/Redline/Amber per design.md §6). When empty, evenly spaced
   * unlabeled Ink ticks are rendered (Login / Report cover usage).
   */
  ticks?: RuleTick[]
  /** Unlabeled ticks when no verdict data applies. */
  tickCount?: number
  children?: ReactNode
  className?: string
}

/**
 * MeasureRule — the structural motif (design.md §6).
 *
 * A vertical ~6px-wide tick-marked rule running down the left edge of
 * key screens. Ticks map to real data on each screen: verdict colors
 * on Compliance Results, a confidence marker on Violation Evidence.
 */
export function MeasureRule({
  ticks = [],
  tickCount = 8,
  children,
  className = '',
}: MeasureRuleProps) {
  const entries: RuleTick[] =
    ticks.length > 0 ? ticks : Array.from({ length: tickCount }, () => 'pass')

  return (
    <div className={`flex items-stretch gap-3 ${className}`} role="img" aria-label="Measure rule">
      <div className="relative w-[6px] border-l border-ink/40" aria-hidden="true">
        {entries.map((tick, index) => (
          <span
            key={index}
            className={`absolute left-0 h-px w-full ${TICK_COLOR[tick]}`}
            style={{ top: `${index * 24}px` }}
          />
        ))}
      </div>
      {children !== undefined && <div className="flex-1 py-1">{children}</div>}
    </div>
  )
}

export default MeasureRule