import { Link } from 'react-router-dom'
import { useState } from 'react'
import { LedgerRow } from '../components/LedgerRow'
import { ComplianceStatusBadge } from '../components/ComplianceStatusBadge'
import { useReviewQueue, useConfirmReview, useOverrideReviewWithMessage } from '../hooks/useReview'
import { getApiErrorMessage } from '../api/client'
import type { LedgerRowStatus } from '../components/LedgerRow'
import type { ComplianceStatus } from '../components/ComplianceStatusBadge'

type ReviewStatus = 'pending' | 'confirmed' | 'corrected'

interface ReviewItem {
  id: string
  inspection_id: string
  field_type: string
  original_value?: Record<string, unknown>
  original_confidence: number
  status: ReviewStatus
  assigned_to?: string | null
}

interface ConfirmMutation {
  mutate: (params: { reviewId: string; body: { confirmed_value?: Record<string, unknown> } }) => void
}

function StatusLabel({ item }: { item: ReviewItem }) {
  if (item.status === 'corrected') {
    return <span className="text-micro text-ink/50">Corrected</span>
  }
  if (item.status === 'confirmed') {
    return <span className="text-micro text-ink/50">Confirmed</span>
  }
  return null
}

function ConfirmButtons({
  item,
  confirmingId,
  setConfirmingId,
  confirm,
  overridingId,
  setOverridingId,
}: {
  item: ReviewItem
  confirmingId: string | null
  setConfirmingId: (id: string | null) => void
  confirm: ConfirmMutation
  overridingId: string | null
  setOverridingId: (id: string | null) => void
}) {
  return (
    <>
      <button
        type="button"
        disabled={confirmingId === item.id}
        onClick={() => {
          setConfirmingId(item.id)
          confirm.mutate({
            reviewId: item.id,
            body: { confirmed_value: item.original_value },
          })
          setConfirmingId(null)
        }}
        className="rounded-control bg-ink text-white px-3 py-1.5 text-micro font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
      >
        {confirmingId === item.id ? 'Confirming…' : 'Confirm'}
      </button>
      <button
        type="button"
        className="rounded-control border border-amber bg-transparent px-3 py-1.5 text-micro text-amber-text hover:bg-amber/10 active:bg-amber/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
        onClick={() => setOverridingId(item.id)}
        disabled={overridingId === item.id}
      >
        {overridingId === item.id ? 'Correcting…' : 'Correct'}
      </button>
    </>
  )
}

export function ManualReviewPage() {
  const { data, isLoading } = useReviewQueue()
  const confirm = useConfirmReview()
  const override = useOverrideReviewWithMessage()
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [overridingId, setOverridingId] = useState<string | null>(null)
  const [correctionReason, setCorrectionReason] = useState('')
  const items: ReviewItem[] = data?.items ?? []
  const pendingCount = data?.pending_count ?? 0
  const ledgerStatus: LedgerRowStatus = 'needs-review'
  const badgeStatus: ComplianceStatus = 'needs-review'

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-ink/50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink/20 border-t-ink" />
        <p className="text-small">Loading review queue…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-serif text-title font-semibold text-ink">Review queue</h1>
        <p className="mt-1 text-small text-ink/60">
          {pendingCount} item{pendingCount !== 1 ? 's' : ''} awaiting human review
        </p>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 border border-ink/10 rounded-surface bg-paper-deep px-6 py-12">
          <p className="text-body text-ink">No items in the review queue.</p>
          <p className="text-small text-ink/50">All clear — no findings need a second look.</p>
        </div>
      ) : (
        <div className="flex flex-col border-t border-ink/10">
          {items.map((item) => {
            return (
              <LedgerRow
                key={item.id}
                status={ledgerStatus}
                leftLabel={item.field_type}
                rightLabel={`${item.original_confidence.toFixed(2)} confidence`}
                rightLink={
                  item.status === 'pending' ? (
                    <Link
                      to={`/inspections/${item.inspection_id}/evidence`}
                      className="text-ink/60 hover:text-ink underline underline-offset-2"
                    >
                      Open evidence
                    </Link>
                  ) : undefined
                }
              >
                <ComplianceStatusBadge status={badgeStatus} />
                <div className="flex items-center gap-2 text-right">
                  {item.status === 'pending' ? (
                    <ConfirmButtons
                      item={item}
                      confirmingId={confirmingId}
                      setConfirmingId={setConfirmingId}
                      confirm={confirm}
                      overridingId={overridingId}
                      setOverridingId={setOverridingId}
                    />
                  ) : (
                    <StatusLabel item={item} />
                  )}
                </div>
              </LedgerRow>
            )
          })}
          {items.map((item) => {
            if (overridingId !== item.id) return null
            return (
              <div className="mx-3 mb-2 flex flex-col gap-3 rounded-surface border border-ink/20 bg-paper-deep p-4">
                <p className="text-label text-ink">Correct this finding</p>
                <textarea
                  className="h-20 resize-y rounded-control border border-ink/20 bg-white p-3 text-body text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                  placeholder="Enter the corrected value…"
                  value={item.original_value ? String(item.original_value['raw'] ?? '') : ''}
                  readOnly
                />
                <label className="flex flex-col gap-1">
                  <span className="text-small text-ink/70">Reason (min 5 characters) — required</span>
                  <input
                    type="text"
                    className="rounded-control border border-ink/20 bg-white px-3 py-2 text-body text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                    value={correctionReason}
                    onChange={(e) => setCorrectionReason(e.target.value)}
                    placeholder="Why is this correction correct?"
                    maxLength={200}
                  />
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setOverridingId(null)
                      setCorrectionReason('')
                    }}
                    className="rounded-control border border-ink bg-transparent px-3 py-1.5 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={correctionReason.length < 5 || override.isPending}
                    onClick={() => {
                      override.mutate({
                        reviewId: item.id,
                        body: { corrected_value: item.original_value ?? { raw: '' }, reason: correctionReason },
                      })
                      setOverridingId(null)
                      setCorrectionReason('')
                    }}
                    className="rounded-control bg-ink text-white px-3 py-1.5 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                  >
                    {override.isPending ? 'Submitting…' : 'Submit correction'}
                  </button>
                </div>
                {override.error && (
                  <p className="text-micro text-redline">{getApiErrorMessage(override.error)}</p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default ManualReviewPage
