import { NavLink, Outlet } from 'react-router-dom';

const links = [
  { to: '/', label: 'Library', emoji: '📚' },
  { to: '/collections', label: 'Collections', emoji: '🗂️' },
  { to: '/timeline', label: 'Timeline', emoji: '🗓️' },
  { to: '/templates', label: 'Templates', emoji: '✒️' },
];

export default function Layout() {
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col md:flex-row">
      <aside className="border-b border-parchment-200 p-4 md:min-h-screen md:w-56 md:border-b-0 md:border-r md:p-6">
        <div className="mb-6">
          <h1 className="font-display text-3xl text-hearth-600">Mathom</h1>
          <p className="mt-1 text-xs text-ink-500">Your Local AI Memory House</p>
        </div>
        <nav className="flex gap-2 md:flex-col">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `rounded-xl px-3 py-2 text-sm ${
                  isActive
                    ? 'bg-hearth-100 font-medium text-hearth-600'
                    : 'text-ink-700 hover:bg-parchment-100'
                }`
              }
            >
              <span className="mr-2" aria-hidden>
                {link.emoji}
              </span>
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
