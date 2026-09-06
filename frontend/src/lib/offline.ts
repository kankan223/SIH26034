/**
 * Offline utilities for the Docket PWA (prd.md §27).
 *
 * Service worker is managed by vite-plugin-pwa (Workbox).
 * This module exposes helpers for:
 *  - Checking online/offline state
 *  - Manual sync trigger
 *  - Whether IndexedDB-backed offline queue is available
 */

export function isOnline(): boolean {
  if (typeof window === 'undefined') return true
  return navigator.onLine
}

export function getOfflineMessage(): string {
  if (typeof window === 'undefined') return ''
  return navigator.onLine
    ? ''
    : 'Working offline — will sync when connected'
}

export function supportsOfflineStorage(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return typeof indexedDB !== 'undefined' && typeof indexedDB.open === 'function'
  } catch {
    return false
  }
}
