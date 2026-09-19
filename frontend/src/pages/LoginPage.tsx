import { useState } from 'react'
import { signIn } from 'aws-amplify/auth'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { AuthCard, ErrorBanner, FormField, SubmitButton } from '../components/auth/AuthFormElements'

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
    <AuthCard title="Welcome back" subtitle="Sign in to your ClauseIQ account">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <ErrorBanner message={error} />

        <FormField
          label="Email address"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />

        <FormField
          label="Password"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
        />

        <SubmitButton loading={loading} loadingText="Signing in...">Sign in</SubmitButton>
      </form>

      <div className="text-center text-sm text-[var(--color-text-muted)]">
        Don't have an account? <Link to="/signup" className="text-[var(--color-accent)] font-medium hover:underline">Create one</Link>
      </div>
    </AuthCard>
  )
}
