import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth';
import { LANGUAGES, useI18n } from '../lib/i18n';
import type { Lang } from '../lib/i18n';
import UploadDialog from './UploadDialog';

const links = [
  { to: '/', labelKey: 'nav.library', emoji: '📚' },
  { to: '/collections', labelKey: 'nav.collections', emoji: '🗂️' },
  { to: '/timeline', labelKey: 'nav.timeline', emoji: '🗓️' },
  { to: '/templates', labelKey: 'nav.templates', emoji: '✒️' },
];

export default function Layout() {
  const { t, lang, setLang } = useI18n();
  const { status, user, isAdmin, isOwner, logout } = useAuth();
  const navigate = useNavigate();
  const [uploadOpen, setUploadOpen] = useState(false);

  const adminLinks = [
    ...(isAdmin ? [{ to: '/admin/users', labelKey: 'nav.users', emoji: '👥' }] : []),
    ...(isOwner ? [{ to: '/admin/settings', labelKey: 'nav.settings', emoji: '🔑' }] : []),
  ];

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col md:flex-row">
      <aside className="border-b border-parchment-200 p-4 md:min-h-screen md:w-56 md:border-b-0 md:border-r md:p-6">
        <div className="mb-6">
          <h1 className="font-display text-3xl text-hearth-600">Mathom</h1>
          <p className="mt-1 text-xs text-ink-500">{t('app.tagline')}</p>
        </div>

        {/* Primary action, reachable from every page. */}
        <button
          onClick={() => setUploadOpen(true)}
          className="btn-primary mb-4 w-full justify-center"
        >
          {t('library.newMathom')}
        </button>

        <nav className="flex flex-wrap gap-2 md:flex-col md:flex-nowrap">
          {[...links, ...adminLinks].map((link) => (
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
              {t(link.labelKey)}
            </NavLink>
          ))}
        </nav>
        <div className="mt-6 md:mt-8">
          <label className="flex items-center gap-2 text-xs text-ink-500">
            <span aria-hidden>🌐</span>
            <span className="sr-only">{t('language.label')}</span>
            <select
              value={lang}
              onChange={(event) => setLang(event.target.value as Lang)}
              aria-label={t('language.label')}
              className="rounded-lg border border-parchment-300 bg-parchment-50 px-2 py-1 text-sm text-ink-700"
            >
              {LANGUAGES.map((entry) => (
                <option key={entry.code} value={entry.code}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {status.auth_enabled && user && (
          <div className="mt-6 border-t border-parchment-200 pt-4 md:mt-8">
            <p className="truncate text-sm font-medium text-ink-700">{user.name || user.email}</p>
            <p className="text-xs text-ink-400">{t(`role.${user.role}`)}</p>
            <button
              onClick={() => void logout()}
              className="mt-2 text-sm text-ink-500 hover:text-hearth-600"
            >
              <span className="mr-1" aria-hidden>
                🚪
              </span>
              {t('auth.signOut')}
            </button>
          </div>
        )}
      </aside>
      <main className="flex-1 p-4 md:p-8">
        <Outlet />
      </main>

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => navigate('/')}
      />
    </div>
  );
}
