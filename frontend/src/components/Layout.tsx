import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth';
import { LANGUAGES, useI18n } from '../lib/i18n';
import type { Lang } from '../lib/i18n';
import UploadDialog from './UploadDialog';

const links = [
  { to: '/', labelKey: 'nav.library', emoji: '📚' },
  { to: '/collections', labelKey: 'nav.collections', emoji: '🗂️' },
  { to: '/tags', labelKey: 'nav.tags', emoji: '🏷️' },
  { to: '/timeline', labelKey: 'nav.timeline', emoji: '🗓️' },
];

export default function Layout() {
  const { t, lang, setLang } = useI18n();
  const { status, user, isAdmin, isOwner, logout } = useAuth();
  const navigate = useNavigate();
  const [uploadOpen, setUploadOpen] = useState(false);

  const adminLinks = [
    ...(!status.auth_enabled || isAdmin
      ? [{ to: '/templates', labelKey: 'nav.templates', emoji: '✒️' }]
      : []),
    ...(isAdmin ? [{ to: '/admin/users', labelKey: 'nav.users', emoji: '👥' }] : []),
    ...(isOwner ? [{ to: '/admin/settings', labelKey: 'nav.settings', emoji: '🔑' }] : []),
  ];

  return (
    <div className="mx-auto flex min-h-screen min-h-[100dvh] max-w-6xl flex-col md:flex-row">
      <aside className="pad-safe-top pad-safe-x border-b-2 border-gild-300/40 bg-moss-900 p-4 text-gild-200 md:pad-safe-top md:min-h-screen md:w-60 md:border-b-0 md:border-r-2 md:p-6">
        <div className="mb-6">
          <h1 className="font-display text-3xl tracking-wide text-gild-300">Mathom</h1>
          <p className="mt-2 text-[10px] uppercase tracking-[0.22em] text-moss-200">
            {t('app.tagline')}
          </p>
        </div>

        {/* Primary action, reachable from every page — the lamp on the desk. */}
        <button
          onClick={() => setUploadOpen(true)}
          className="mb-5 inline-flex w-full items-center justify-center gap-2 rounded bg-gild-300 px-4 py-2 text-xs font-semibold uppercase tracking-[0.1em] text-moss-900 transition-colors hover:bg-gild-200"
        >
          {t('library.newMathom')}
        </button>

        <nav className="flex flex-wrap gap-1 md:flex-col md:flex-nowrap">
          {[...links, ...adminLinks].map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `border-l-2 px-3 py-2 text-xs uppercase tracking-[0.12em] transition-colors ${
                  isActive
                    ? 'border-gild-300 bg-white/5 font-semibold text-gild-300'
                    : 'border-transparent text-gild-200 hover:text-white'
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
          <label className="flex items-center gap-2 text-xs text-moss-200">
            <span aria-hidden>🌐</span>
            <span className="sr-only">{t('language.label')}</span>
            <select
              value={lang}
              onChange={(event) => setLang(event.target.value as Lang)}
              aria-label={t('language.label')}
              className="rounded border border-white/15 bg-moss-800 px-2 py-1 text-sm text-gild-200"
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
          <div className="mt-6 border-t border-white/15 pt-4 md:mt-8">
            <p className="truncate text-sm font-medium text-gild-200">{user.name || user.email}</p>
            <p className="text-[10px] uppercase tracking-[0.14em] text-moss-200">
              {t(`role.${user.role}`)}
            </p>
            <button
              onClick={() => void logout()}
              className="mt-2 text-sm text-moss-200 hover:text-gild-300"
            >
              <span className="mr-1" aria-hidden>
                🚪
              </span>
              {t('auth.signOut')}
            </button>
          </div>
        )}
      </aside>
      <main className="pad-safe-bottom pad-safe-x flex-1 p-4 md:pad-safe-bottom md:p-8">
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
