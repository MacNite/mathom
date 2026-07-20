import { useState } from 'react';

import { ApiError, api } from '../lib/api';
import { useAuth } from '../lib/auth';

export default function Onboarding() {
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
      setError('Passwords do not match');
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
      setError(err instanceof Error ? err.message : 'Setup failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={submit} className="card w-full max-w-md space-y-3">
        <h1 className="font-display text-2xl">Set up Mathom</h1>
        <p className="text-sm text-ink-500">
          Create the first administrator account. Passwords must be at least 12 characters.
        </p>
        <input aria-label="Display name" placeholder="Display name" value={name}
          onChange={(event) => setName(event.target.value)} className="w-full rounded border p-2" />
        <input aria-label="Email" required type="email" placeholder="Email" value={email}
          onChange={(event) => setEmail(event.target.value)} className="w-full rounded border p-2" />
        <input aria-label="Password" required minLength={12} type="password" placeholder="Password"
          value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded border p-2" />
        <input aria-label="Confirm password" required type="password" placeholder="Confirm password"
          value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="w-full rounded border p-2" />
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button disabled={submitting} className="btn-primary w-full disabled:opacity-60">
          {submitting ? 'Creating administrator…' : 'Create administrator'}
        </button>
      </form>
    </div>
  );
}
