import { useCallback, useEffect, useState } from 'react';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
import type { Role, User } from '../lib/types';

const ROLES: Role[] = ['admin', 'user'];

export default function Users() {
  const { t } = useI18n();
  const toast = useToast();
  const { user: me, isAdmin, refresh: refreshAuth } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [mustChangePassword, setMustChangePassword] = useState(true);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(
    () =>
      api
        .listUsers()
        .then(setUsers)
        .catch((err) => setError(err instanceof Error ? err.message : t('users.loadError')))
        .finally(() => setLoading(false)),
    [t],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const applyChange = async (target: User, changes: { role?: Role; is_active?: boolean }) => {
    setError('');
    try {
      await api.updateUser(target.id, changes);
      await refresh();
      // Keep the header in sync if the Owner edited their own account.
      if (target.id === me?.id) await refreshAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  const changeRole = (target: User, role: Role) => applyChange(target, { role });
  const toggleActive = (target: User) => applyChange(target, { is_active: !target.is_active });

  const createUser = async (event: React.FormEvent) => {
    event.preventDefault();
    if (password !== confirmation) {
      setError(t('users.passwordMismatch'));
      return;
    }

    setCreating(true);
    setError('');
    try {
      await api.createUser({
        name,
        email,
        password,
        must_change_password: mustChangePassword,
      });
      setName('');
      setEmail('');
      setPassword('');
      setConfirmation('');
      setMustChangePassword(true);
      await refresh();
      toast.success(t('users.created'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('users.createError'));
    } finally {
      setCreating(false);
    }
  };

  const remove = async (target: User) => {
    if (!window.confirm(t('users.confirmDelete', { email: target.email }))) return;
    setError('');
    try {
      await api.deleteUser(target.id);
      await refresh();
      toast.success(t('users.deleted'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  return (
    <div>
      <h2 className="font-display text-2xl text-ink-900">{t('users.title')}</h2>
      <p className="mt-1 text-sm text-ink-500">{t('users.subtitle')}</p>

      {error && (
        <p className="mt-4 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="mt-4 text-sm text-ink-500">{t('common.loading')}</p>}

      <form onSubmit={createUser} className="card mt-6 max-w-2xl space-y-4">
        <div>
          <h3 className="font-display text-lg text-ink-900">{t('users.add')}</h3>
          <p className="mt-1 text-sm text-ink-500">{t('users.addHint')}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm text-ink-700">
            {t('users.name')}
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="input mt-1"
              autoComplete="name"
            />
          </label>
          <label className="block text-sm text-ink-700">
            {t('users.email')}
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="input mt-1"
              autoComplete="email"
            />
          </label>
          <label className="block text-sm text-ink-700">
            {t('users.password')}
            <input
              required
              minLength={12}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="input mt-1"
              autoComplete="new-password"
            />
          </label>
          <label className="block text-sm text-ink-700">
            {t('users.confirmPassword')}
            <input
              required
              minLength={12}
              type="password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="input mt-1"
              autoComplete="new-password"
            />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={mustChangePassword}
            onChange={(event) => setMustChangePassword(event.target.checked)}
          />
          {t('users.mustChangePassword')}
        </label>
        <div>
          <button disabled={creating} className="btn-primary disabled:opacity-60">
            {creating ? t('users.creating') : t('users.create')}
          </button>
        </div>
      </form>

      <div className="mt-6 space-y-3">
        {users.map((entry) => {
          const isSelf = me?.id === entry.id;
          return (
            <div
              key={entry.id}
              className="card flex flex-wrap items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-ink-900">
                  {entry.name || entry.email}
                  {isSelf && <span className="ml-2 text-xs text-ink-400">({t('users.you')})</span>}
                </p>
                <p className="truncate text-sm text-ink-500">{entry.email}</p>
                <p className="text-xs text-ink-400">
                  {t('users.lastLogin')}:{' '}
                  {entry.last_login_at
                    ? new Date(entry.last_login_at).toLocaleString()
                    : t('users.never')}
                </p>
              </div>

              <div className="flex items-center gap-2">
                {isAdmin ? (
                  <select
                    value={entry.role}
                    onChange={(event) => changeRole(entry, event.target.value as Role)}
                    aria-label={t('users.role')}
                    className="rounded-lg border border-parchment-300 bg-parchment-50 px-2 py-1 text-sm text-ink-700"
                  >
                    {ROLES.map((role) => (
                      <option key={role} value={role}>
                        {t(`role.${role}`)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="rounded-lg bg-parchment-100 px-2 py-1 text-sm text-ink-700">
                    {t(`role.${entry.role}`)}
                  </span>
                )}

                <button
                  onClick={() => toggleActive(entry)}
                  disabled={isSelf}
                  className="rounded-lg border border-parchment-300 px-2 py-1 text-sm text-ink-700 hover:bg-parchment-100 disabled:opacity-40"
                >
                  {entry.is_active ? t('users.deactivate') : t('users.activate')}
                </button>

                {!isSelf && (
                  <button
                    onClick={() => remove(entry)}
                    className="text-sm text-ink-400 hover:text-red-700"
                  >
                    {t('users.delete')}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
