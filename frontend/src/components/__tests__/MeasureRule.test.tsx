import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MeasureRule } from '../MeasureRule'

describe('MeasureRule (design.md §6)', () => {
  it('renders a vertical rule with the 6px width', () => {
    render(<MeasureRule ticks={['pass', 'fail', 'review']} />)
    const rule = document.querySelector('.relative')
    expect(rule).not.toBeNull()
    expect(rule!.className).toContain('w-[6px]')
  })

  it('colors ticks by verdict (Teal/Redline/Amber)', () => {
    render(<MeasureRule ticks={['pass', 'fail', 'review']} />)
    const ticks = Array.from(document.querySelectorAll('span'))
    const classes = ticks.map((t) => t.className)
    expect(classes.some((c) => c.includes('bg-verify'))).toBe(true)
    expect(classes.some((c) => c.includes('bg-redline'))).toBe(true)
    expect(classes.some((c) => c.includes('bg-amber'))).toBe(true)
  })

  it('renders evenly spaced ticks when no verdicts provided', () => {
    render(<MeasureRule tickCount={8} />)
    const ticks = Array.from(document.querySelectorAll('span'))
    expect(ticks).toHaveLength(8)
  })

  it('renders children as the legend/label area', () => {
    render(
      <MeasureRule ticks={['pass']}>
        <h1>Compliance Results</h1>
      </MeasureRule>,
    )
    expect(screen.getByText('Compliance Results')).toBeInTheDocument()
  })
})