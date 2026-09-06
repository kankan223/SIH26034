
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ManualReviewPage } from '../ManualReviewPage'

vi.mock('../../hooks/useReview', () => ({
  useReviewQueue: vi.fn(() => ({
    data: {
      items: [
        {
          id: 'REV-0001',
          inspection_id: 'INSP-2026-000742',
          field_type: 'mrp_format',
          original_value: { raw: '999', currency: 'INR', unit: '₹' },
          original_confidence: 0.42,
          status: 'pending',
          assigned_to: null,
        },
        {
          id: 'REV-0002',
          inspection_id: 'INSP-2026-000741',
          field_type: 'net_quantity',
          original_value: { raw: '500', unit: 'g' },
          original_confidence: 0.61,
          status: 'confirmed',
          assigned_to: null,
        },
      ],
      total: 2,
      pending_count: 1,
    },
    isLoading: false,
    error: null,
  })),
  useConfirmReview: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  }),
  useOverrideReviewWithMessage: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  }),
}))

function getUseReviewQueueMock() {
  return require('../../hooks/useReview').useReviewQueue as ReturnType<typeof vi.fn>
}

function getUseOverrideMock() {
  return require('../../hooks/useReview').useOverrideReviewWithMessage as ReturnType<typeof vi.fn>
}

describe('ManualReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the queue header with pending count', () => {
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText(/1 item awaiting human review/i)).toBeInTheDocument()
  })

  it('renders a ledger row per review item', () => {
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText('mrp_format')).toBeInTheDocument()
    expect(screen.getByText('net_quantity')).toBeInTheDocument()
  })

  it('shows confirm and correct buttons for pending items', () => {
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /Confirm/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Correct/i })).toBeInTheDocument()
  })

  it('renders confirmed label for already-confirmed items', () => {
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText('Confirmed')).toBeInTheDocument()
  })

  it('opens the correction form when Correct is clicked', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /Correct/i }))
    expect(screen.getByText(/Correct this finding/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Why is this correction correct/i)).toBeInTheDocument()
  })

  it('submits the correction when the reason is long enough', async () => {
    const overrideMock = vi.fn()
    getUseOverrideMock().mockReturnValue({
      mutate: overrideMock,
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    })

    const user = userEvent.setup()
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /Correct/i }))
    const reasonInput = screen.getByPlaceholderText(/Why is this correction correct/i)
    await user.type(reasonInput, 'Label reading was wrong, verified against packaging.')

    await user.click(screen.getByRole('button', { name: /Submit correction/i }))
    expect(overrideMock).toHaveBeenCalledWith(
      expect.objectContaining({ reviewId: 'REV-0001' }),
      expect.any(Object),
    )
  })

  it('disables submit when reason is too short', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /Correct/i }))
    await user.type(screen.getByPlaceholderText(/Why is this correction correct/i), 'too')

    const submitButton = screen.getByRole('button', { name: /Submit correction/i })
    expect(submitButton).toBeDisabled()
  })

  it('shows an empty-queue state when there are no items', () => {
    getUseReviewQueueMock().mockReturnValue({
      data: { items: [], total: 0, pending_count: 0 },
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText(/No items in the review queue/i)).toBeInTheDocument()
  })
})
