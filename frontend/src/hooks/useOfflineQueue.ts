import { useEffect, useRef, useState } from 'react'

export interface QueuedRequest {
  id: string
  method: 'POST' | 'PUT' | 'PATCH'
  url: string
  body: unknown
  timestamp: number
  retryCount: number
}

const DB_NAME = 'docket-offline'
const STORE_NAME = 'pending-requests'
const MAX_RETRIES = 3

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onerror = () => reject(request.error)
    request.onsuccess = () => resolve(request.result)
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' })
      }
    }
  })
}

async function putRequest(entry: QueuedRequest): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.put(entry)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

async function getAllRequests(): Promise<QueuedRequest[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const req = store.getAll()
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function deleteRequest(id: string): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.delete(id)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

function generateId(): string {
  return `qr_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function useOfflineQueue() {
  const [isOnline, setIsOnline] = useState(true)
  const [queueSize, setQueueSize] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const inFlightRef = useRef<Set<string>>(new Set())
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    setIsOnline(navigator.onLine)

    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)

    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return

    const updateQueueSize = async () => {
      try {
        const items = await getAllRequests()
        setQueueSize(items.length)
      } catch {
        // IndexedDB may not be available
      }
    }

    updateQueueSize()
    // Retry sync every 30s when online
    intervalRef.current = setInterval(() => {
      if (isOnline) {
        void syncQueue()
      }
    }, 30_000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [isOnline])

  async function syncQueue(): Promise<void> {
    if (!isOnline || syncing) return
    setSyncing(true)
    inFlightRef.current.clear()

    try {
      const items = await getAllRequests()
      for (const item of items) {
        if (item.retryCount >= MAX_RETRIES) {
          await deleteRequest(item.id)
          continue
        }
        if (inFlightRef.current.has(item.id)) continue

        inFlightRef.current.add(item.id)
        try {
          const response = await fetch(item.url, {
            method: item.method,
            headers: {
              'Content-Type': 'application/json',
            },
            body: item.body ? JSON.stringify(item.body) : undefined,
          })

          if (response.ok) {
            await deleteRequest(item.id)
          } else {
            // Bump retry count
            const updated = { ...item, retryCount: item.retryCount + 1 }
            await putRequest(updated)
          }
        } catch {
          // Network error — leave in queue for next retry
          const updated = { ...item, retryCount: item.retryCount + 1 }
          await putRequest(updated)
        } finally {
          inFlightRef.current.delete(item.id)
        }
      }
    } finally {
      setSyncing(false)
    }
  }

  async function queueRequest(
    method: 'POST' | 'PUT' | 'PATCH',
    url: string,
    body: unknown,
  ): Promise<void> {
    const entry: QueuedRequest = {
      id: generateId(),
      method,
      url,
      body,
      timestamp: Date.now(),
      retryCount: 0,
    }
    await putRequest(entry)
    setQueueSize((prev) => prev + 1)

    if (isOnline) {
      void syncQueue()
    }
  }

  return { isOnline, queueSize, syncing, queueRequest, syncQueue }
}
