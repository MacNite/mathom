import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import { AuthProvider, useAuth } from './auth';
import { api } from './api';
import type { AuthStatus } from './types';

vi.mock('./api', () => ({ api: { authStatus: vi.fn(), logout: vi.fn() } }));

const mockedStatus = api.authStatus as unknown as ReturnType<typeof vi.fn>;

function Probe() {
  const { loading, status, isOwner, isAdmin } = useAuth();
  if (loading) return <span>loading</span>;
  return <span>{`${status.auth_enabled}:${status.authenticated}:${isAdmin}:${isOwner}`}</span>;
}

const ownerStatus: AuthStatus = {
  auth_enabled: true,
  configured: true,
  authenticated: true,
  login_url: '/api/auth/login',
  user: {
    id: 1,
    email: 'owner@example.com',
    name: 'Owner',
    role: 'admin',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    last_login_at: null,
  },
};

describe('AuthProvider', () => {
  it('exposes owner/admin flags from the backend status', async () => {
    mockedStatus.mockResolvedValue(ownerStatus);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText('true:true:true:true')).toBeInTheDocument());
  });

  it('falls back to the disabled single-user default when status fails', async () => {
    mockedStatus.mockRejectedValue(new Error('offline'));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText('false:false:false:false')).toBeInTheDocument());
  });
});
