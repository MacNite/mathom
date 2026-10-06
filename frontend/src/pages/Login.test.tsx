import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { useAuth } from '../lib/auth';
import { I18nProvider } from '../lib/i18n';
import type { AuthStatus } from '../lib/types';
import Login from './Login';

vi.mock('../lib/api', () => ({ api: { localLogin: vi.fn() } }));
vi.mock('../lib/auth', () => ({ useAuth: vi.fn() }));

const base: AuthStatus = {
  auth_enabled: true,
  configured: true,
  authenticated: false,
  authentik_configured: true,
  login_url: '/api/auth/login/authentik',
  user: null,
};

function renderWith(status: AuthStatus) {
  (useAuth as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    status,
    refresh: vi.fn(),
    login: vi.fn(),
  });
  return render(
    <I18nProvider>
      <Login />
    </I18nProvider>,
  );
}

describe('Login', () => {
  afterEach(() => window.history.replaceState(null, '', '/'));

  it('offers both password and Authentik sign-in by default', () => {
    renderWith({ ...base, local_login_available: true });
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByText('Continue with Authentik')).toBeInTheDocument();
  });

  it('hides the password form when password sign-in is off', () => {
    renderWith({ ...base, local_login_available: false });
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
    expect(screen.getByText('Continue with Authentik')).toBeInTheDocument();
  });

  it('explains an Authentik sign-in error from the callback', () => {
    window.history.replaceState(null, '', '/?auth_error=email_conflict');
    renderWith({ ...base, local_login_available: false });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'did not confirm it as verified',
    );
  });

  it('falls back to a generic message for unknown error codes', () => {
    window.history.replaceState(null, '', '/?auth_error=access_denied');
    renderWith(base);
    expect(screen.getByRole('alert')).toHaveTextContent('Sign-in failed');
  });
});
