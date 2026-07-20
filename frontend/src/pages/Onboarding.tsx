import { useState } from 'react';

import { ApiError, api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

export default function Onboarding() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
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
      await api.onboarding(name, email, password, confirmation);
      await refresh();
    } catch (err) {
      // A completed first request can race with a second tap. Refreshing the
      // status moves the visitor to sign-in instead of trapping them here.
      if (err instanceof ApiError && err.status === 409) {
        await refresh();
        return;
      }
      setError(err instanceof Error ? err.message : t('onboarding.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={submit} className="card w-full max-w-md space-y-3">
        <h1 className="font-display text-2xl">{t('onboarding.title')}</h1>
        <p className="text-sm text-ink-500">{t('onboarding.subtitle')}</p>
        <label className="block text-sm text-ink-700">
          {t('onboarding.name')}
          <input
            aria-label={t('onboarding.name')}
            placeholder={t('onboarding.name')}
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="name"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('onboarding.email')}
          <input
            aria-label={t('onboarding.email')}
            required
            type="email"
            placeholder={t('onboarding.email')}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('onboarding.password')}
          <input
            aria-label={t('onboarding.password')}
            required
            minLength={12}
            type="password"
            placeholder={t('onboarding.password')}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('onboarding.confirmPassword')}
          <input
            aria-label={t('onboarding.confirmPassword')}
            required
            type="password"
            placeholder={t('onboarding.confirmPassword')}
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
        <button disabled={submitting} className="btn-primary w-full justify-center disabled:opacity-60">
          {submitting ? t('onboarding.creating') : t('onboarding.create')}
        </button>
      </form>
    </div>
  );
}
