import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Camera, FileText, Inbox, LayoutDashboard, LogOut } from 'lucide-react'
import { useLogout } from '../hooks/useAuth'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/capture', label: 'New inspection', icon: Camera },
  { to: '/reviews', label: 'Review queue', icon: Inbox },
  { to: '/reports', label: 'Reports', icon: FileText },
]

const navItemClass = ({ isActive }: { isActive: boolean }) =>
  'flex items-center gap-2 border-b border-ink/10 px-4 py-2.5 text-small text-ink ' +
  (isActive ? 'border-l-4 border-l-verify font-medium' : 'border-l-4 border-l-transparent')

/**
 * Layout — the app shell (design.md §8).
 *
 * Desktop sidebar / mobile bottom nav, ledger styling throughout,
 * Docket wordmark in Source Serif 4. Child routes render via <Outlet />.
 */
export function Layout() {
  const logout = useLogout()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen bg-paper">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-ink/10 md:flex">
        <div className="border-b border-ink/10 px-4 py-3">
          <span className="font-serif text-section font-semibold text-ink">Docket</span>
        </div>
        <nav className="flex-1" aria-label="Primary">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={navItemClass}>
              <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          type="button"
          onClick={handleLogout}
          className="flex items-center gap-2 border-t border-ink/10 px-4 py-3 text-small text-ink/70"
        >
          <LogOut size={16} strokeWidth={1.5} aria-hidden="true" />
          Log out
        </button>
      </aside>

      {/* Mobile bottom nav */}
      <nav
        className="fixed inset-x-0 bottom-0 z-10 flex border-t border-ink/10 bg-paper md:hidden"
        aria-label="Primary"
      >
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              'flex min-h-[44px] flex-1 items-center justify-center gap-1 px-1 text-micro ' +
              (isActive ? 'text-ink' : 'text-ink/50')
            }
          >
            <Icon size={20} strokeWidth={1.5} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <main className="min-w-0 flex-1 p-6 pb-20 md:pb-6">
        <Outlet />
      </main>
    </div>
  )
}

export default Layout