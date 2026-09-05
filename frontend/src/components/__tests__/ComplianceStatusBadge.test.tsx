import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ComplianceStatusBadge } from '../ComplianceStatusBadge'

describe('ComplianceStatusBadge (design.md §7.1)', () => {
  it('renders sentence-case labels', () => {
    render(<ComplianceStatusBadge status="compliant" />)
    expect(screen.getByText('Compliant')).toBeInTheDocument()
  })

  it.each([
    ['compliant', 'bg-verify', 'text-white'],
    ['violation', 'bg-redline', 'text-white'],
    // Amber fill uses Ink Navy text per the contrast rule (design.md §1.1)
    ['needs-review', 'bg-amber', 'text-ink'],
  ] as const)('applies the %s fill and text tones', (status, fillClass, textClass) => {
    render(<ComplianceStatusBadge status={status} />)
    const badge = screen.getByText(status === 'needs-review' ? 'Needs review' : status === 'compliant' ? 'Compliant' : 'Violation')
    expect(badge.className).toContain(fillClass)
    expect(badge.className).toContain(textClass)
  })
})