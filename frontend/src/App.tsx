import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactElement } from 'react'
import { getAuthToken } from './api/client'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { InspectionLayout } from './components/InspectionLayout'
import { InspectionDetailPage } from './pages/InspectionDetailPage'
import { ProcessingScreenPage } from './pages/ProcessingScreenPage'
import { ExtractedInfoPage } from './pages/ExtractedInfoPage'
import { ComplianceResultsPage } from './pages/ComplianceResultsPage'

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
        <Route
          path="/inspections/:id"
          element={
            <RequireAuth>
              <InspectionLayout />
            </RequireAuth>
          }
        >
          <Route index element={<InspectionDetailPage />} />
          <Route path="processing" element={<ProcessingScreenPage />} />
          <Route path="extracted" element={<ExtractedInfoPage />} />
          <Route path="compliance" element={<ComplianceResultsPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<div className="p-6 text-ink">Page not found</div>} />
    </Routes>
  )
}

export default App