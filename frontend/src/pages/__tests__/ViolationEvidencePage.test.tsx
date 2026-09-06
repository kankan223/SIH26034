
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ViolationEvidencePage } from '../ViolationEvidencePage'
import { useInspection } from '../../hooks/useInspection'

vi.mock('../../hooks/useInspection', () => ({
  useInspection: vi.fn(),
}))
vi.mock('../../api/client', () => ({
  getApiErrorMessage: () => '',
  apiClient: { get: vi.fn(), post: vi.fn() },
}))

describe('ViolationEvidencePage', () => {
  const mockViolation = {
    id: 'viol-1',
    rule_key: 'mrp_format',
    field_name: 'MRP',
    verdict: 'fail',
    confidence: 0.42,
  }

  const mockInspection = {
    id: 'INSP-2026-000742',
    status: 'needs-review',
    compliance: {
      violations: [mockViolation],
      per_field_compliance: [
        { field_type: 'MRP', confidence: 0.42 },
      ],
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the violation header with inspection id', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockInspection,
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByText(/Violation mrp_format/)).toBeInTheDocument()
    expect(screen.getByText(/INSP-2026-000742/)).toBeInTheDocument()
  })

  it('renders the evidence card component', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockInspection,
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByText('No evidence image')).toBeInTheDocument()
    expect(screen.getByText('mrp_format')).toBeInTheDocument()
  })

  it('renders the rule citation in serif', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockInspection,
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByText(/Rule mrp_format, Legal Metrology/)).toBeInTheDocument()
  })

  it('renders the confirm and correct action buttons', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockInspection,
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByRole('button', { name: /Confirm violation/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Correct this finding/i })).toBeInTheDocument()
  })

  it('renders the MeasureRule confidence tick', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: mockInspection,
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByRole('img')).toBeInTheDocument()
  })

  it('shows a loading state while the inspection loads', () => {
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByText(/Loading evidence/i)).toBeInTheDocument()
  })

  it('shows an error state when the inspection fetch fails', () => {
    const networkError = new Error('Network Error')
    ;(useInspection as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: networkError,
    })

    render(<MemoryRouter><ViolationEvidencePage /></MemoryRouter>)

    expect(screen.getByText('Could not load evidence')).toBeInTheDocument()
  })
})
