import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactElement } from 'react'
import { getAuthToken } from './api/client'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'

function RequireAuth({ children }: { children: ReactElement }) {
  if (!getAuthToken()) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Phase 8.3+ pages mount here */}
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<div className="p-6 text-ink">Page not found</div>} />
    </Routes>
  )
}

export default App