import { Routes, Route, Navigate } from 'react-router-dom'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<div>Login Page — TBD</div>} />
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<div>Page not found</div>} />
    </Routes>
  )
}

export default App
