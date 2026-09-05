import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Layout } from '../Layout'

vi.mock('../../hooks/useAuth', () => ({
  useLogout: () => vi.fn(),
}))

describe('Layout (app shell, design.md §8)', () => {
  it('renders the Docket wordmark and primary navigation', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>,
    )
    expect(screen.getByText('Docket')).toBeInTheDocument()
    // Desktop sidebar + mobile bottom nav both render the nav items.
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('New inspection').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Review queue').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Reports').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Log out')).toBeInTheDocument()
  })

  it('marks the active nav item with the verify ledger tick', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Layout />
      </MemoryRouter>,
    )
    const links = screen.getAllByRole('link', { name: /Dashboard/ })
    // The desktop sidebar link carries the 4px verify tick; the mobile
    // bottom-nav link is the compact variant.
    const desktopLink = links.find((link) => link.className.includes('border-l-verify'))
    expect(desktopLink).toBeDefined()
    expect(desktopLink!.className).toContain('border-l-verify')
  })
})