import { useState } from 'react'
import { signUp, confirmSignUp } from 'aws-amplify/auth'
import { Link, useNavigate } from 'react-router-dom'

export default function SignupPage() {
  const navigate = useNavigate()
  
  // This state memory box remembers which of the 2 steps we are currently on
  const [step, setStep] = useState<'SIGNUP' | 'CONFIRM'>('SIGNUP')
  
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Step 1: Submit Email & Password
  async function handleSignup(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await signUp({ username: email, password })
      // Move to Step 2!
      setStep('CONFIRM')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to sign up.')
    } finally {
      setLoading(false)
    }
  }

  // Step 2: Submit the 6-digit code
  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await confirmSignUp({ username: email, confirmationCode: code })
      // Success! Send them to the login screen
      navigate('/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to confirm code.')
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
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)] m-0 mt-2">
            {step === 'SIGNUP' ? 'Create an account' : 'Verify your email'}
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] m-0">
            {step === 'SIGNUP' ? 'Sign up for ClauseIQ' : 'Enter the 6-digit code sent to your email'}
          </p>
        </div>

        {error && <div className="p-3 bg-red-900/20 border border-red-900/50 text-red-500 rounded text-sm">{error}</div>}

        {step === 'SIGNUP' ? (
          <form onSubmit={handleSignup} className="flex flex-col gap-4">
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
              {loading ? 'Creating...' : 'Create account'}
            </button>
            <div className="text-center text-sm text-[var(--color-text-muted)]">
              Already have an account? <Link to="/" className="text-[var(--color-accent)] font-medium hover:underline">Sign in</Link>
            </div>
          </form>
        ) : (
          <form onSubmit={handleConfirm} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[var(--color-text-muted)]">Verification Code</label>
              <input
                type="text"
                className="w-full p-2.5 bg-black/20 border border-[var(--color-border-subtle)] rounded-md text-[var(--color-text-primary)] text-sm outline-none focus:border-[var(--color-accent)] transition-colors text-center tracking-[0.5em]"
                placeholder="123456"
                value={code}
                onChange={e => setCode(e.target.value)}
                required
              />
            </div>
            <button 
              type="submit" 
              disabled={loading}
              className="w-full p-2.5 mt-2 bg-[var(--color-accent)] hover:bg-indigo-600 text-white rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Verifying...' : 'Verify Code'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
