import { Navigate, Route, Routes } from 'react-router-dom';
import type { ReactElement } from 'react';

import Layout from './components/Layout';
import { useAuth } from './lib/auth';
import { useI18n } from './lib/i18n';
import AuthentikSettings from './pages/AuthentikSettings';
import Collections from './pages/Collections';
import Library from './pages/Library';
import Login from './pages/Login';
import Onboarding from './pages/Onboarding';
import MathomDetail from './pages/MathomDetail';
import ShareTarget from './pages/ShareTarget';
import Templates from './pages/Templates';
import Timeline from './pages/Timeline';
import Users from './pages/Users';

export default function App() {
  const { t } = useI18n();
  const { loading, status, isAdmin } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-500">
        {t('auth.loading')}
      </div>
    );
  }

  // When auth is enabled and nobody is signed in, the whole app is the login gate.
  if (status.auth_enabled && !status.authenticated) {
    return status.onboarding_required ? <Onboarding /> : <Login />;
  }

  const guard = (allowed: boolean, element: ReactElement): ReactElement =>
    allowed ? element : <Navigate to="/" replace />;

  return (
    <Routes>
      {/* Web Share Target landing — rendered without the app chrome. */}
      <Route path="share-target" element={<ShareTarget />} />
      <Route element={<Layout />}>
        <Route index element={<Library />} />
        <Route path="mathoms/:id" element={<MathomDetail />} />
        <Route path="templates" element={<Templates />} />
        <Route path="collections" element={<Collections />} />
        <Route path="timeline" element={<Timeline />} />
        <Route path="admin/users" element={guard(isAdmin, <Users />)} />
        <Route path="admin/settings" element={guard(isAdmin, <AuthentikSettings />)} />
      </Route>
    </Routes>
  );
}
