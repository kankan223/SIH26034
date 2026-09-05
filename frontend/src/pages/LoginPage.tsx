import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage } from '../api/client'
import { MeasureRule } from '../components/MeasureRule'
import { useLogin } from '../hooks/useAuth'

/**
 * LoginPage (design.md §8.1).
 *
 * Staff login, not a landing page: display-serif "Docket" headline, the
 * unlabeled Measure Rule down the left edge, Plex Sans labels above
 * inputs (never placeholder-as-label, §7.6). On success the JWT is held
 * in memory and the user is redirected to the Dashboard.
 */
export function LoginPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    login.mutate(
      { email, password },
      {
        onSuccess: () => navigate('/dashboard', { replace: true }),
      },
    )
  }

  const errorMessage = login.isError ? getApiErrorMessage(login.error, 'Invalid email or password') : null

  return (
    <div className="flex min-h-screen">
      <MeasureRule tickCount={10} className="min-h-screen w-6 shrink-0 pt-12" />

      <div className="flex flex-1 items-center justify-center px-6">
        <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4" aria-label="Sign in">
          <div className="mb-6">
            <h1 className="font-serif text-display text-ink">Docket</h1>
            <p className="text-label text-ink/60">Legal Metrology Compliance</p>
          </div>

          <div>
            <label htmlFor="email" className="mb-1 block text-label text-ink">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-[4px] border border-ink/30 bg-paper-deep px-3 py-2 text-body text-ink"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-label text-ink">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-[4px] border border-ink/30 bg-paper-deep px-3 py-2 text-body text-ink"
            />
          </div>

          {errorMessage && (
            <p role="alert" className="text-small text-redline">
              {errorMessage}
            </p>
          )}

          <button
            type="submit"
            disabled={login.isPending}
            className="w-full rounded-[4px] bg-ink px-4 py-2 text-body font-medium text-white transition-colors duration-150 disabled:opacity-60"
          >
            {login.isPending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage