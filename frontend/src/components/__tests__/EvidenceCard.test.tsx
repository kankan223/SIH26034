import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidenceCard } from '../EvidenceCard'

const bbox = { x1: 100, y1: 50, x2: 300, y2: 250 }

describe('EvidenceCard (design.md §7.3)', () => {
  it('renders violation ID in mono and detected/expected values', () => {
    render(
      <EvidenceCard
        violationId="LM-001 · MRP"
        detected="999"
        expected='MRP with "inclusive of all taxes"'
        ruleCitation="Rule 6(1)(f), LMPC Rules 2011"
      />,
    )
    expect(screen.getByText('LM-001 · MRP')).toBeInTheDocument()
    expect(screen.getByText(/999/)).toBeInTheDocument()
    expect(screen.getByText(/inclusive of all taxes/)).toBeInTheDocument()
    expect(screen.getByText('Rule 6(1)(f), LMPC Rules 2011')).toBeInTheDocument()
  })

  it('renders the evidence image when provided', () => {
    render(
      <EvidenceCard
        violationId="VIO-1"
        imageUrl="https://minio.local/crop.png"
        bbox={bbox}
        imageWidth={400}
        imageHeight={300}
      />,
    )
    const img = screen.getByAltText('Evidence crop for VIO-1') as HTMLImageElement
    expect(img).toBeInTheDocument()
    expect(img.src).toContain('minio.local')
  })

  it('draws the bounding box overlay as an SVG rect', () => {
    render(<EvidenceCard violationId="VIO-1" bbox={bbox} imageWidth={400} imageHeight={300} />)
    const rect = document.querySelector('svg rect.bbox-draw')
    expect(rect).not.toBeNull()
    // x1=100/400 → 25%, y1=50/300 → ~16.67%
    expect(rect!.getAttribute('x')).toBe('25')
    expect(rect!.getAttribute('y')).toContain('16.6')
    // stroke-draw animation per design.md §5
    expect(rect!.getAttribute('stroke')).toBe('var(--color-redline)')
  })

  it('shows a placeholder when no image is available', () => {
    render(<EvidenceCard violationId="VIO-2" />)
    expect(screen.getByText('No evidence image')).toBeInTheDocument()
  })
})