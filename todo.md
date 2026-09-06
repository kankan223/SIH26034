### Subphase 8.5: Routing & App Shell (COMPLETE)

#### Task 8.5.1: Implement React Router, layout, and offline queue (COMPLETE)

**Description:**
Set up React Router with all page routes, the app shell layout (sidebar/navigation), and the offline capture queue per prd.md §27.

**Input Required:**
- prd.md §22 (all 15 pages with navigation)
- prd.md §27 (offline mode: IndexedDB queue, sync when online)
- design.md §10 (responsive: mobile-first for inspector flows, desktop-first for admin flows)

**Processing:**
- [x] Update `frontend/src/App.tsx` with React Router:
  - Route definitions for all 15 pages
  - Protected routes (redirect to login if unauthenticated)
  - Role-based route access (admin pages only for admin role)
- [x] Create `frontend/src/components/Layout.tsx`:
  - Sidebar navigation with page links
  - Mobile-responsive: bottom nav on mobile, sidebar on desktop
  - Measure Rule on left edge (collapses to 3px on mobile per design.md §10)
  - User info and logout in header
- [x] Create `frontend/src/hooks/useOfflineQueue.ts`:
  - IndexedDB queue for inspections captured offline
  - Sync queue when connectivity returns
  - Amber Flag offline banner per design.md §10
- [x] Create `frontend/src/lib/offline.ts`:
  - Service worker registration
  - IndexedDB utilities

**Output:**
- Updated `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `frontend/src/hooks/useOfflineQueue.ts`
- `frontend/src/lib/offline.ts`

**Verification Tasks:**
1. [x] All 15 routes accessible via navigation
2. [x] Unauthenticated access redirects to login
3. [x] Admin routes return 403 or redirect for non-admin users
4. [x] Mobile layout shows bottom nav, desktop shows sidebar
5. [x] Measure Rule collapses to 3px on mobile
6. [x] Offline banner appears when network is lost

**Regression Check:** All 540 backend tests + 58 Vitest tests pass, tsc 0 errors, build OK

**Git Instructions:**
```bash
git add frontend/src/App.tsx frontend/src/components/OfflineBanner.tsx frontend/src/components/Layout.tsx frontend/src/hooks/useOfflineQueue.ts frontend/src/lib/offline.ts frontend/src/hooks/__tests__/useOfflineQueue.test.ts
git commit -m "feat(frontend): offline capture queue and final router configuration

- useOfflineQueue hook: IndexedDB-backed queue for POST/PUT/PATCH requests
- OfflineBanner component: Amber Flag strip per design.md §10
- lib/offline.ts: online check, offline message, IndexedDB support check
- App.tsx: OfflineBanner rendered above Routes, all 15 routes wired
- Layout.tsx: desktop sidebar + mobile bottom nav already in place
- PWA service worker via vite-plugin-pwa caches app shell for offline use
- 58 Vitest tests passing, tsc 0 errors, build OK

See: prd.md §27 (offline mode), design.md §10 (responsive layout)
```
git push origin feature/phase-8.5-offline-queue
```
