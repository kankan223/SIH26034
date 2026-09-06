
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ReportPage } from '../ReportPage'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const hooksDir = path.resolve(__dirname, '../../hooks')

vi.mock(path.join(hooksDir, 'useInspection'), () => ({
  useInspection: vi.fn(),
}))

describe('ReportPage', () => {
  let mockUseInspection: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseInspection = vi.mocked(require(path.join(hooksDir, 'useInspection')).useInspection)
    mockUseInspection.mockReturnValue({
      data: {
        id: 'INSP-2026-000742',
        product_name: 'Britannia Good Day Biscuits 200g',
        overall_status: 'COMPLIANT',
        compliance: {
          per_field_compliance: [
            { field_type: 'manufacturer_details', status: 'PASS', rule_version_id: 'RULEV-0017', confidence: 0.92 },
            { field_type: 'net_quantity', status: 'PASS', rule_version_id: 'RULEV-0018', confidence: 0.88 },
            { field_type: 'mrp_format', status: 'PASS', rule_version_id: 'RULEV-0061', confidence: 0.85 },
          ],
        },
      },
      isLoading: false,
      error: null,
    })
  })

  it('renders the report header with inspection id', () => {
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText(/Compliance report/)).toBeInTheDocument()
    expect(screen.getByText('INSP-2026-000742')).toBeInTheDocument()
  })

  it('renders the compliant status banner', () => {
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText(/Compliant — no violations found/i)).toBeInTheDocument()
  })

  it('renders declaration rows with pass status', () => {
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText('manufacturer_details')).toBeInTheDocument()
    expect(screen.getByText('Pass')).toBeInTheDocument()
  })

  it('renders download, print, and regenerate actions', () => {
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Print report/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Regenerate/i })).toBeInTheDocument()
  })

  it('renders pending banner for inspections still being analyzed', () => {
    mockUseInspection.mockReturnValue({
      data: { id: 'INSP-0001', product_name: 'Test Soda 330ml', overall_status: 'PENDING', compliance: { per_field_compliance: [] } },
      isLoading: false,
      error: null,
    })
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText(/Pending — analysis not yet complete/i)).toBeInTheDocument()
  })
})
