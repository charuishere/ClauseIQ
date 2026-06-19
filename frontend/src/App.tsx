import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'

// A security wrapper to protect the Dashboard route
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  
  if (isLoading) {
    return <div className="h-screen flex items-center justify-center bg-[var(--color-bg-base)] text-white">Loading...</div>
  }
  
  if (!user) {
    return <Navigate to="/" />
  }
  
  return <>{children}</>
}

// A wrapper to prevent logged-in users from seeing the Login/Signup pages
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  
  if (isLoading) {
    return <div className="h-screen flex items-center justify-center bg-[var(--color-bg-base)] text-white">Loading...</div>
  }
  
  if (user) {
    return <Navigate to="/dashboard" />
  }
  
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={
            <PublicRoute>
              <LoginPage />
            </PublicRoute>
          } />
          <Route path="/signup" element={
            <PublicRoute>
              <SignupPage />
            </PublicRoute>
          } />
          
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          } />
          
          {/* This route catches when you click an agreement in the sidebar! */}
          <Route path="/agreements/:id" element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
