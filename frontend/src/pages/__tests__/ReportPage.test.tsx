import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ReportPage } from '../ReportPage'
import { useInspection } from '../../hooks/useInspection'

// ── Mocks ──────────────────────────────────────────────────────────────────
vi.mock('../../hooks/useInspection', () => ({
  useInspection: vi.fn(() => ({
    data: {
      id: 'INSP-2026-000742',
      product_name: 'Britannia Good Day Biscuits 200g',
      overall_status: 'COMPLIANT' as const,
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
  })),
}))

// ── Shared mock data ───────────────────────────────────────────────────────
const compliantInspection = {
  id: 'INSP-2026-000742',
  product_name: 'Britannia Good Day Biscuits 200g',
  overall_status: 'COMPLIANT' as const,
  compliance: {
    per_field_compliance: [
      { field_type: 'manufacturer_details', status: 'PASS', rule_version_id: 'RULEV-0017', confidence: 0.92 },
      { field_type: 'net_quantity', status: 'PASS', rule_version_id: 'RULEV-0018', confidence: 0.88 },
      { field_type: 'mrp_format', status: 'PASS', rule_version_id: 'RULEV-0061', confidence: 0.85 },
    ],
  },
}

function mockInspectionData(override?: Partial<typeof compliantInspection>) {
  return {
    data: override ?? compliantInspection,
    isLoading: false,
    error: null,
  }
}

// ── Tests ──────────────────────────────────────────────────────────────────
describe('ReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue(mockInspectionData())
  })

  it('renders the report header with inspection id', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue(mockInspectionData())
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText('Compliance report')).toBeInTheDocument()
    expect(screen.getAllByText('INSP-2026-000742')).toHaveLength(2)
  })

  it('renders the compliant status banner', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue(mockInspectionData())
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText('Compliant — no violations found')).toBeInTheDocument()
  })

  it('renders declaration rows with pass status', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue(mockInspectionData())
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText('manufacturer_details')).toBeInTheDocument()
    expect(screen.getAllByText('Pass')).toHaveLength(3)
  })

  it('renders download, print, and regenerate actions', () => {
    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Download PDF' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Print report' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Regenerate' })).toBeInTheDocument()
  })

  it('renders pending banner for inspections still being analyzed', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: {
        id: 'INSP-0001',
        product_name: 'Test Soda 330ml',
        overall_status: 'PENDING',
        compliance: { per_field_compliance: [] },
      },
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ReportPage /></MemoryRouter>)
    expect(screen.getByText('Pending — analysis not yet complete')).toBeInTheDocument()
  })
})
