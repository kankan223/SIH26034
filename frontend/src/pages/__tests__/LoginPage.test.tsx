import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { LoginPage } from '../LoginPage'

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  login: {
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null as unknown,
  },
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../hooks/useAuth', () => ({
  useLogin: () => mocks.login,
}))

describe('LoginPage (design.md §8.1)', () => {
  it('renders the Docket headline and sign-in form', () => {
    render(<LoginPage />)
    expect(screen.getByText('Docket')).toBeInTheDocument()
    expect(screen.getByText('Legal Metrology Compliance')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('renders the Measure Rule motif on the left edge', () => {
    render(<LoginPage />)
    expect(screen.getByRole('img', { name: 'Measure rule' })).toBeInTheDocument()
  })

  it('submits credentials and navigates to the dashboard on success', () => {
    mocks.login.mutate.mockImplementationOnce(
      (_creds: unknown, opts: { onSuccess?: () => void }) => {
        opts.onSuccess?.()
      },
    )
    render(<LoginPage />)
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'officer@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(mocks.login.mutate).toHaveBeenCalledWith(
      { email: 'officer@example.com', password: 'secret' },
      expect.anything(),
    )
    expect(mocks.navigate).toHaveBeenCalledWith('/dashboard', { replace: true })
  })

  it('shows an inline error when credentials are rejected', () => {
    mocks.login.isError = true
    mocks.login.error = Object.assign(new Error('Invalid email or password'), {
      response: { status: 401 },
    })
    render(<LoginPage />)
    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveTextContent('Invalid email or password')
    mocks.login.isError = false
    mocks.login.error = null
  })
})