import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { I18nProvider } from "../lib/i18n";
import { ToastProvider } from "../lib/toast";
import type { ApiToken, InboxStatus, MyInboxFolder } from "../lib/types";
import Automation from "./Automation";

const { api } = vi.hoisted(() => ({
  api: {
    listApiTokens: vi.fn(),
    createApiToken: vi.fn(),
    deleteApiToken: vi.fn(),
    getInboxStatus: vi.fn(),
    getMyInboxFolder: vi.fn(),
    renameMyInboxFolder: vi.fn(),
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
  per_user: false,
  running: true,
  last_scan_at: "2026-09-28T10:00:00Z",
  last_error: "",
  imported_total: 12,
  waiting: 1,
  folders: [],
  unmatched_folders: [],
  loose_files: 0,
};

const myFolder: MyInboxFolder = {
  enabled: true,
  per_user: true,
  inbox_name: "alice",
  path: "/inbox/alice",
  present: false,
  imported: 3,
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
  api.getMyInboxFolder.mockResolvedValue({ ...myFolder, enabled: false });
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

it("lets a user see and rename their own inbox folder", async () => {
  api.getMyInboxFolder.mockResolvedValue(myFolder);
  api.renameMyInboxFolder.mockResolvedValue({
    ...myFolder,
    inbox_name: "alice-phone",
    path: "/inbox/alice-phone",
  });
  renderPage();

  expect(await screen.findByText("/inbox/alice")).toBeInTheDocument();
  expect(screen.getByText(/3 recordings imported from it/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Folder name"), { target: { value: "alice-phone" } });
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await waitFor(() => expect(api.renameMyInboxFolder).toHaveBeenCalledWith("alice-phone"));
  expect(await screen.findByText("/inbox/alice-phone")).toBeInTheDocument();
});

it("shows admins every user's folder and what is left unassigned", async () => {
  api.getInboxStatus.mockResolvedValue({
    ...inboxOn,
    per_user: true,
    folders: [{ name: "alice", user: "Alice", present: true, imported: 4 }],
    unmatched_folders: ["carol"],
    loose_files: 2,
  });
  renderPage();
  expect(await screen.findByText("alice/")).toBeInTheDocument();
  expect(screen.getByText(/match no account and are left alone: carol/)).toBeInTheDocument();
  expect(screen.getByText(/2 files lie directly in the watched folder/)).toBeInTheDocument();
});
