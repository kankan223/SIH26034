import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ManualReviewPage } from '../ManualReviewPage'
import {
  useReviewQueue,
  useConfirmReview,
  useOverrideReviewWithMessage,
} from '../../hooks/useReview'

// ── Mocks ──────────────────────────────────────────────────────────────────
vi.mock('../../hooks/useReview', () => ({
  useReviewQueue: vi.fn(),
  useConfirmReview: vi.fn(),
  useOverrideReviewWithMessage: vi.fn(),
}))

// ── Shared mock data ───────────────────────────────────────────────────────
const reviewItems = [
  {
    id: 'REV-0001',
    inspection_id: 'INSP-2026-000742',
    field_type: 'mrp_format',
    original_value: { raw: '999', currency: 'INR', unit: '₹' },
    original_confidence: 0.42,
    status: 'pending' as const,
    assigned_to: null,
  },
  {
    id: 'REV-0002',
    inspection_id: 'INSP-2026-000741',
    field_type: 'net_quantity',
    original_value: { raw: '500', unit: 'g' },
    original_confidence: 0.61,
    status: 'confirmed' as const,
    assigned_to: null,
  },
]

function mockQueueData(override?: Partial<typeof reviewItems>) {
  return {
    data: {
      items: override ? [override] : reviewItems,
      total: override ? 1 : 2,
      pending_count: override ? 1 : 1,
    },
    isLoading: false,
    error: null,
  }
}

// ── Tests ──────────────────────────────────────────────────────────────────
describe('ManualReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: queue has items, confirm and override are no-op spies
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    ;(useConfirmReview as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    })
    ;(useOverrideReviewWithMessage as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    })
  })

  it('renders the queue header with pending count', () => {
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText(/1 item awaiting human review/i)).toBeInTheDocument()
  })

  it('renders a ledger row per review item', () => {
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText(/mrp_format/i)).toBeInTheDocument()
    expect(screen.getByText(/net_quantity/i)).toBeInTheDocument()
  })

  it('shows confirm and correct buttons for pending items', () => {
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /correct/i })).toBeInTheDocument()
  })

  it('renders confirmed label for already-confirmed items', () => {
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText(/confirmed/i)).toBeInTheDocument()
  })

  it('opens the correction form when Correct is clicked', async () => {
    const user = userEvent.setup()
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /correct/i }))
    expect(screen.getByText(/correct this finding/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/why is this correction correct/i)).toBeInTheDocument()
  })

  it('submits the correction when the reason is long enough', async () => {
    const user = userEvent.setup()
    const overrideSpy = vi.fn()
    ;(useOverrideReviewWithMessage as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: overrideSpy,
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    })
    const confirmSpy = vi.fn()
    ;(useConfirmReview as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: confirmSpy,
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    })

    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /correct/i }))
    const reasonInput = screen.getByPlaceholderText(/why is this correction correct/i)
    await user.type(reasonInput, 'Label reading was wrong, verified against packaging.')

    await user.click(screen.getByRole('button', { name: /submit correction/i }))
    await waitFor(() => {
      expect(overrideSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          reviewId: 'REV-0001',
          body: expect.objectContaining({
            corrected_value: { raw: '999', currency: 'INR', unit: '₹' },
            reason: 'Label reading was wrong, verified against packaging.',
          }),
        }),
      )
    })
  })

  it('disables submit when reason is too short', async () => {
    const user = userEvent.setup()
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue(mockQueueData())
    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /correct/i }))
    await user.type(
      screen.getByPlaceholderText(/why is this correction correct/i),
      'too',
    )

    const submitButton = screen.getByRole('button', { name: /submit correction/i })
    expect(submitButton).toBeDisabled()
  })

  it('shows an empty-queue state when there are no items', () => {
    ;(useReviewQueue as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [], total: 0, pending_count: 0 },
      isLoading: false,
      error: null,
    })

    render(<MemoryRouter><ManualReviewPage /></MemoryRouter>)
    expect(screen.getByText(/no items in the review queue/i)).toBeInTheDocument()
  })
})
