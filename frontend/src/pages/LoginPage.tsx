import { useState } from 'react'
import { signIn } from 'aws-amplify/auth'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const { checkUser } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    
    try {
      // This sends the credentials securely to AWS Cognito
      await signIn({ username: email, password })
      await checkUser()
      navigate('/dashboard')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to sign in.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[var(--color-bg-base)] p-4">
      <div className="w-full max-w-sm bg-[var(--color-bg-panel)] border border-[var(--color-border-subtle)] rounded-xl p-8 shadow-xl flex flex-col gap-6">
        
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="w-10 h-10 bg-[var(--color-accent)] text-white font-bold text-xl rounded-lg flex items-center justify-center">
            C
          </div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)] m-0 mt-2">Welcome back</h1>
          <p className="text-sm text-[var(--color-text-muted)] m-0">Sign in to your ClauseIQ account</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && <div className="p-3 bg-red-900/20 border border-red-900/50 text-red-500 rounded text-sm">{error}</div>}

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--color-text-muted)]">Email address</label>
            <input
              type="email"
              className="w-full p-2.5 bg-black/20 border border-[var(--color-border-subtle)] rounded-md text-[var(--color-text-primary)] text-sm outline-none focus:border-[var(--color-accent)] transition-colors"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--color-text-muted)]">Password</label>
            <input
              type="password"
              className="w-full p-2.5 bg-black/20 border border-[var(--color-border-subtle)] rounded-md text-[var(--color-text-primary)] text-sm outline-none focus:border-[var(--color-accent)] transition-colors"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="w-full p-2.5 mt-2 bg-[var(--color-accent)] hover:bg-indigo-600 text-white rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="text-center text-sm text-[var(--color-text-muted)]">
          Don't have an account? <Link to="/signup" className="text-[var(--color-accent)] font-medium hover:underline">Create one</Link>
        </div>
      </div>
    </div>
  )
}
