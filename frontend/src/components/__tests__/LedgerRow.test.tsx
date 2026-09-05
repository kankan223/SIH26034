import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { LedgerRow } from '../LedgerRow'

describe('LedgerRow (design.md §3.2)', () => {
  it('renders children and the hairline ledger structure', () => {
    render(
      <LedgerRow status="compliant">
        <span>Britannia Good Day — Cashew Cookies 200g</span>
        <span>✓ Compliant</span>
      </LedgerRow>,
    )
    expect(screen.getByText('Britannia Good Day — Cashew Cookies 200g')).toBeInTheDocument()
    expect(screen.getByText('✓ Compliant')).toBeInTheDocument()
  })

  it.each([
    ['compliant', 'border-l-verify'],
    ['violation', 'border-l-redline'],
    ['needs-review', 'border-l-amber'],
    ['neutral', 'border-l-transparent'],
  ] as const)('renders the %s status tick color', (status, expectedClass) => {
    render(<LedgerRow status={status}>Row</LedgerRow>)
    const row = screen.getByText('Row').closest('div')!
    expect(row.className).toContain(expectedClass)
    expect(row.className).toContain('border-l-4')
  })

  it('calls onClick when provided and renders as a button', () => {
    const onClick = vi.fn()
    render(<LedgerRow status="violation" onClick={onClick}>Clickable</LedgerRow>)
    const row = screen.getByRole('button', { name: 'Clickable' })
    fireEvent.click(row)
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})