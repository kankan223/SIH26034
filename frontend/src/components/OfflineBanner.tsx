import { useOfflineQueue } from '../hooks/useOfflineQueue'

/**
 * OfflineBanner — Amber Flag strip per design.md §10.
 *
 * Shows when the browser reports offline. Does not show when online
 * even if the queue has items (the queue syncs silently in the background).
 */
export function OfflineBanner() {
  const { isOnline, queueSize, syncing } = useOfflineQueue()

  if (isOnline) return null

  return (
    <div
      className="flex items-center gap-2 rounded-surface bg-amber/10 border border-amber/20 px-4 py-2 text-amber-text text-small font-medium"
      role="status"
      aria-live="polite"
    >
      <svg
        className="shrink-0 h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <line x1="1" y1="1" x2="23" y2="23" />
        <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
        <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
        <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
        <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
        <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
        <line x1="12" y1="20" x2="12.01" y2="20" />
      </svg>
      <span>Offline — will sync when connected</span>
      {queueSize > 0 && (
        <span className="ml-auto rounded-full bg-amber/20 px-2 py-0.5 text-micro">
          {queueSize} pending{queueSize !== 1 ? 's' : ''}
        </span>
      )}
      {syncing && (
        <span className="ml-2 h-4 w-4 animate-spin rounded-full border-2 border-amber/30 border-t-amber" />
      )}
    </div>
  )
}

export default OfflineBanner
