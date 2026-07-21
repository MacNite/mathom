import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";

import Layout from "./components/Layout";
import { useAuth } from "./lib/auth";
import { useI18n } from "./lib/i18n";
import AuthentikSettings from "./pages/AuthentikSettings";
import Collections from "./pages/Collections";
import ForcePasswordChange from "./pages/ForcePasswordChange";
import Library from "./pages/Library";
import Login from "./pages/Login";
import Onboarding from "./pages/Onboarding";
import MathomDetail from "./pages/MathomDetail";
import ShareTarget from "./pages/ShareTarget";
import Templates from "./pages/Templates";
import Timeline from "./pages/Timeline";
import Users from "./pages/Users";
import Register from "./pages/Register";

export default function App() {
  const { t } = useI18n();
  const { loading, status, user, isAdmin } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-500">
        {t("auth.loading")}
      </div>
    );
  }

  // When auth is enabled and nobody is signed in, the whole app is the login
  // gate — except for the public invitation flow. An invitee following the link
  // in their email is signed out by definition, so `/register` must render
  // before the gate; otherwise they land on the login page (which they cannot
  // use yet) instead of setting their password.
  if (status.auth_enabled && !status.authenticated) {
    return (
      <Routes>
        <Route path="register" element={<Register />} />
        <Route
          path="*"
          element={status.onboarding_required ? <Onboarding /> : <Login />}
        />
      </Routes>
    );
  }

  // A signed-in account flagged for a mandatory password change is held at the
  // change screen until it sets a new password — no other route renders.
  if (status.auth_enabled && user?.must_change_password) {
    return <ForcePasswordChange />;
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
        <Route
          path="templates"
          element={guard(!status.auth_enabled || isAdmin, <Templates />)}
        />
        <Route path="collections" element={<Collections />} />
        <Route path="timeline" element={<Timeline />} />
        <Route path="register" element={<Register />} />
        <Route path="admin/users" element={guard(isAdmin, <Users />)} />
        <Route
          path="admin/settings"
          element={guard(isAdmin, <AuthentikSettings />)}
        />
      </Route>
    </Routes>
  );
}
