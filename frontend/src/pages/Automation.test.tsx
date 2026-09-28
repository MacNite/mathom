import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { I18nProvider } from "../lib/i18n";
import { ToastProvider } from "../lib/toast";
import type { ApiToken, InboxStatus } from "../lib/types";
import Automation from "./Automation";

const { api } = vi.hoisted(() => ({
  api: {
    listApiTokens: vi.fn(),
    createApiToken: vi.fn(),
    deleteApiToken: vi.fn(),
    getInboxStatus: vi.fn(),
    scanInboxNow: vi.fn(),
  },
}));

vi.mock("../lib/api", () => ({ api }));

const token: ApiToken = {
  id: 7,
  name: "Tasker",
  prefix: "mth_abcdefgh",
  scope: "ingest",
  created_at: "2026-09-01T10:00:00Z",
  expires_at: null,
  last_used_at: null,
};

const inboxOn: InboxStatus = {
  enabled: true,
  path: "/inbox",
  owner_email: "",
  running: true,
  last_scan_at: "2026-09-28T10:00:00Z",
  last_error: "",
  imported_total: 12,
  waiting: 1,
};

function renderPage() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <Automation />
      </ToastProvider>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.listApiTokens.mockResolvedValue([]);
  api.getInboxStatus.mockResolvedValue({ ...inboxOn, enabled: false });
});

it("creates a token and shows it once, with a ready-to-use example", async () => {
  api.createApiToken.mockResolvedValue({ ...token, token: "mth_secret-value" });
  api.listApiTokens.mockResolvedValueOnce([]).mockResolvedValueOnce([token]);
  renderPage();

  fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Tasker" } });
  fireEvent.change(screen.getByLabelText("Expires"), { target: { value: "90" } });
  fireEvent.click(screen.getByRole("button", { name: "Create token" }));

  await waitFor(() => expect(api.createApiToken).toHaveBeenCalledWith("Tasker", 90));
  expect(await screen.findByText("mth_secret-value")).toBeInTheDocument();
  expect(screen.getByText(/Bearer mth_secret-value/)).toBeInTheDocument();
  expect(await screen.findByText("mth_abcdefgh…")).toBeInTheDocument();
});

it("revokes a token after confirmation", async () => {
  api.listApiTokens.mockResolvedValue([token]);
  api.deleteApiToken.mockResolvedValue(undefined);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
  await waitFor(() => expect(api.deleteApiToken).toHaveBeenCalledWith(7));
});

it("shows the watched folder status and its last problem", async () => {
  api.getInboxStatus.mockResolvedValue({ ...inboxOn, last_error: "Inbox paused: no owner" });
  renderPage();
  expect(await screen.findByText("/inbox")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("no owner");
  fireEvent.click(screen.getByRole("button", { name: "Scan now" }));
  await waitFor(() => expect(api.scanInboxNow).toHaveBeenCalled());
});

it("explains how to enable the watched folder when it is off", async () => {
  renderPage();
  expect(await screen.findByText(/set MATHOM_INBOX_DIR/)).toBeInTheDocument();
});
