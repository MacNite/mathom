import { useState } from 'react';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

// Shown when an account is flagged must_change_password (an admin-created
// account or a reset): the app is gated behind this screen until a new
// password is set. Changing it revokes every session, so the user signs in
// again afterwards with the new password.
export default function ForcePasswordChange() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (password !== confirmation) {
      setError(t('onboarding.passwordMismatch'));
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await api.changeMyPassword(current, password);
      // Changing the password revokes the current session; refreshing moves the
      // user to sign-in, where the new password takes effect.
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('forcePassword.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={submit} className="card w-full max-w-md space-y-3">
        <h1 className="font-display text-2xl">{t('forcePassword.title')}</h1>
        <p className="text-sm text-ink-500">{t('forcePassword.subtitle')}</p>
        <label className="block text-sm text-ink-700">
          {t('forcePassword.current')}
          <input
            aria-label={t('forcePassword.current')}
            required
            type="password"
            placeholder={t('forcePassword.current')}
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            autoComplete="current-password"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('forcePassword.new')}
          <input
            aria-label={t('forcePassword.new')}
            required
            minLength={12}
            type="password"
            placeholder={t('forcePassword.new')}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('forcePassword.confirm')}
          <input
            aria-label={t('forcePassword.confirm')}
            required
            type="password"
            placeholder={t('forcePassword.confirm')}
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="new-password"
            className="input mt-1"
          />
        </label>
        {error && (
          <p className="text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <button
          disabled={submitting}
          className="btn-primary w-full justify-center disabled:opacity-60"
        >
          {submitting ? t('forcePassword.saving') : t('forcePassword.submit')}
        </button>
      </form>
    </div>
  );
}
