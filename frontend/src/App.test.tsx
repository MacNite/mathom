import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import App from "./App";
import { api } from "./lib/api";
import { AuthProvider } from "./lib/auth";
import { I18nProvider } from "./lib/i18n";
import { ToastProvider } from "./lib/toast";
import type { AuthStatus } from "./lib/types";

vi.mock("./lib/api", () => ({
  api: { authStatus: vi.fn(), acceptInvitation: vi.fn(), logout: vi.fn() },
}));

const mockedStatus = api.authStatus as unknown as ReturnType<typeof vi.fn>;

// Auth is on, an admin already exists (onboarding not required), and the
// visitor is signed out — exactly an invitee following the email link.
const signedOut: AuthStatus = {
  auth_enabled: true,
  configured: true,
  authenticated: false,
  onboarding_required: false,
  login_url: "/api/auth/login",
  user: null,
};

function renderAt(path: string) {
  return render(
    <I18nProvider>
      <ToastProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </AuthProvider>
      </ToastProvider>
    </I18nProvider>,
  );
}

describe("App invitation routing", () => {
  it("renders the registration page for a signed-out invitee, not the login gate", async () => {
    mockedStatus.mockResolvedValue(signedOut);
    renderAt("/register?token=abc123");
    // The invitee must reach the password form — the old gate sent them to login.
    await waitFor(() =>
      expect(screen.getByText("Set your Mathom password")).toBeInTheDocument(),
    );
  });

  it("still shows the login gate for other routes when signed out", async () => {
    mockedStatus.mockResolvedValue(signedOut);
    renderAt("/");
    await waitFor(() =>
      expect(
        screen.queryByText("Set your Mathom password"),
      ).not.toBeInTheDocument(),
    );
  });
});
