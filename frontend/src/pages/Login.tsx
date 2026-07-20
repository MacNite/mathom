import { useState } from 'react';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useI18n } from '../lib/i18n';

export default function Login() {
  const { t } = useI18n();
  const { status, refresh, login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.localLogin(email, password);
      await refresh();
    } catch {
      setError(t('login.invalid'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="card w-full max-w-md text-center">
        <div className="mb-2 text-4xl" aria-hidden>
          🏡
        </div>
        <h1 className="font-display text-3xl text-hearth-600">Mathom</h1>
        <h2 className="mt-4 font-display text-xl">{t('login.title')}</h2>
        <form onSubmit={submit} className="mt-5 space-y-3 text-left">
          <label className="block text-sm text-ink-700">
            {t('login.email')}
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              className="input mt-1"
            />
          </label>
          <label className="block text-sm text-ink-700">
            {t('login.password')}
            <input
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              className="input mt-1"
            />
          </label>
          {error && (
            <p className="text-sm text-red-700" role="alert">
              {error}
            </p>
          )}
          <button disabled={busy} className="btn-primary w-full justify-center disabled:opacity-60">
            {busy ? t('login.signingIn') : t('login.signIn')}
          </button>
        </form>
        {status.authentik_configured && (
          <button onClick={login} className="btn-ghost mt-3 w-full justify-center">
            {t('login.authentik')}
          </button>
        )}
      </div>
    </div>
  );
}
