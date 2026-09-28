import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { I18nProvider } from "../lib/i18n";
import { ToastProvider } from "../lib/toast";
import type { NotificationSettings } from "../lib/types";
import Notifications from "./Notifications";

const { api } = vi.hoisted(() => ({
  api: {
    getNotificationSettings: vi.fn(),
    updateNotificationSettings: vi.fn(),
    sendTestNotification: vi.fn(),
    getWebPushKey: vi.fn(),
    addPushSubscription: vi.fn(),
    removePushSubscription: vi.fn(),
  },
}));

vi.mock("../lib/api", () => ({ api }));

const settings: NotificationSettings = {
  enabled: true,
  notify_on_ready: true,
  notify_on_error: true,
  ntfy_url: "",
  webhook_url: "",
  ntfy_token_set: false,
  webhook_secret_set: false,
  web_push_devices: 0,
  public_base_url_set: false,
};

function renderPage() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <Notifications />
      </ToastProvider>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getNotificationSettings.mockResolvedValue(settings);
});

it("explains that push needs HTTPS in an insecure context", async () => {
  // jsdom is not a secure context, which is exactly the plain-HTTP LAN case.
  renderPage();
  expect(
    await screen.findByText("Push notifications need Mathom to be opened over HTTPS."),
  ).toBeInTheDocument();
  expect(screen.getByText("Set PUBLIC_BASE_URL so ntfy and webhook messages carry a clickable link.")).toBeInTheDocument();
});

it("saves channels and shows per-channel test results", async () => {
  api.updateNotificationSettings.mockResolvedValue({
    ...settings,
    ntfy_url: "https://ntfy.example.com/mathom",
    ntfy_token_set: true,
  });
  api.sendTestNotification.mockResolvedValue([
    { channel: "ntfy", ok: true, detail: "sent" },
    { channel: "webhook", ok: false, detail: "answered 500" },
  ]);
  renderPage();

  fireEvent.change(await screen.findByLabelText("Topic URL"), {
    target: { value: "https://ntfy.example.com/mathom" },
  });
  fireEvent.change(screen.getByLabelText("Access token"), { target: { value: "tk" } });
  fireEvent.click(screen.getByRole("button", { name: "Save channels" }));

  await waitFor(() =>
    expect(api.updateNotificationSettings).toHaveBeenCalledWith({
      ntfy_url: "https://ntfy.example.com/mathom",
      ntfy_token: "tk",
      webhook_url: "",
      webhook_secret: "",
    }),
  );
  // The saved token is never echoed back into the field.
  await waitFor(() => expect(screen.getByLabelText("Access token")).toHaveValue(""));

  fireEvent.click(screen.getByRole("button", { name: "Send a test" }));
  expect(await screen.findByText(/ntfy — sent/)).toBeInTheDocument();
  expect(screen.getByText(/Webhook — answered 500/)).toBeInTheDocument();
});

it("toggles the ready notification preference", async () => {
  api.updateNotificationSettings.mockResolvedValue({ ...settings, notify_on_ready: false });
  renderPage();
  fireEvent.click(await screen.findByLabelText("A Mathom is ready"));
  await waitFor(() =>
    expect(api.updateNotificationSettings).toHaveBeenCalledWith({ notify_on_ready: false }),
  );
});

it("tells the user when the server switched notifications off", async () => {
  api.getNotificationSettings.mockResolvedValue({ ...settings, enabled: false });
  renderPage();
  expect(await screen.findByRole("status")).toHaveTextContent("turned off on this server");
  expect(screen.getByRole("button", { name: "Save channels" })).toBeDisabled();
});
