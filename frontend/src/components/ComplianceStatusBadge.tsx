import { Check, Flag, X } from 'lucide-react'

export type ComplianceStatus = 'compliant' | 'violation' | 'needs-review'

const STATUS_CONFIG: Record<
  ComplianceStatus,
  { label: string; icon: typeof Check; className: string }
> = {
  compliant: {
    label: 'Compliant',
    icon: Check,
    className: 'bg-verify text-white',
  },
  violation: {
    label: 'Violation',
    icon: X,
    className: 'bg-redline text-white',
  },
  'needs-review': {
    label: 'Needs review',
    icon: Flag,
    // Amber fill with Ink Navy text per the contrast rule in design.md §1.1
    className: 'bg-amber text-ink',
  },
}

interface ComplianceStatusBadgeProps {
  status: ComplianceStatus
  className?: string
}

/**
 * ComplianceStatusBadge (design.md §7.1).
 *
 * Sentence-case chip with fill background and left-aligned icon:
 * ✓ Compliant (Verify Teal), ✕ Violation (Redline),
 * ⚑ Needs review (Amber Flag with Ink Navy text). Never outline-only.
 */
export function ComplianceStatusBadge({ status, className = '' }: ComplianceStatusBadgeProps) {
  const { label, icon: Icon, className: tone } = STATUS_CONFIG[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[4px] px-2 py-0.5 text-small font-medium ${tone} ${className}`}
    >
      <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
      {label}
    </span>
  )
}

export default ComplianceStatusBadge