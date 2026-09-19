import { useState } from 'react'
import { signUp, confirmSignUp } from 'aws-amplify/auth'
import { Link, useNavigate } from 'react-router-dom'
import { AuthCard, ErrorBanner, FormField, SubmitButton } from '../components/auth/AuthFormElements'

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
    <AuthCard
      title={step === 'SIGNUP' ? 'Create an account' : 'Verify your email'}
      subtitle={step === 'SIGNUP' ? 'Sign up for ClauseIQ' : 'Enter the 6-digit code sent to your email'}
    >
      <ErrorBanner message={error} />

      {step === 'SIGNUP' ? (
        <form onSubmit={handleSignup} className="flex flex-col gap-4">
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
          <SubmitButton loading={loading} loadingText="Creating...">Create account</SubmitButton>
          <div className="text-center text-sm text-[var(--color-text-muted)]">
            Already have an account? <Link to="/" className="text-[var(--color-accent)] font-medium hover:underline">Sign in</Link>
          </div>
        </form>
      ) : (
        <form onSubmit={handleConfirm} className="flex flex-col gap-4">
          <FormField
            label="Verification Code"
            type="text"
            className="text-center tracking-[0.5em]"
            placeholder="123456"
            value={code}
            onChange={e => setCode(e.target.value)}
            required
          />
          <SubmitButton loading={loading} loadingText="Verifying...">Verify Code</SubmitButton>
        </form>
      )}
    </AuthCard>
  )
}
