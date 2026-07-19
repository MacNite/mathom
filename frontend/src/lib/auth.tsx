import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { api } from './api';
import type { AuthStatus, User } from './types';

// Default status used before the first fetch resolves and if it ever fails:
// auth disabled means the app renders as the original single-user archive.
const DISABLED: AuthStatus = {
  auth_enabled: false,
  configured: false,
  authenticated: false,
  onboarding_required: false,
  local_login_available: false,
  authentik_configured: false,
  login_url: '/api/auth/login',
  user: null,
};

interface AuthValue {
  loading: boolean;
  status: AuthStatus;
  user: User | null;
  isAdmin: boolean;
  isOwner: boolean;
  refresh: () => Promise<void>;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue>({
  loading: true,
  status: DISABLED,
  user: null,
  isAdmin: false,
  isOwner: false,
  refresh: async () => undefined,
  login: () => undefined,
  logout: async () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(DISABLED);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.authStatus());
    } catch {
      // Network/parse failure: fall back to the safe single-user default.
      setStatus(DISABLED);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(() => {
    const next = window.location.pathname + window.location.search;
    window.location.href = `${status.login_url}?next=${encodeURIComponent(next)}`;
  }, [status.login_url]);

  const logout = useCallback(async () => {
    await api.logout();
    await refresh();
  }, [refresh]);

  const value = useMemo<AuthValue>(() => {
    const role = status.user?.role;
    return {
      loading,
      status,
      user: status.user,
      isAdmin: role === 'admin',
      isOwner: role === 'admin',
      refresh,
      login,
      logout,
    };
  }, [loading, status, refresh, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  return useContext(AuthContext);
}
