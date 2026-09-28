# Notifications — "your Mathom is ready"

When a recording has finished transcribing and summarizing, Mathom can tell you
about it, with a link straight to the transcript. It can also tell you when a
recording couldn't be finished. Each person turns this on for themselves under
**🔔 Notifications**. Until they do, nothing is sent.

| Channel | What you get | Leaves your network? |
| --- | --- | --- |
| **Push (this device)** | A system notification from the Mathom PWA. Tapping it opens the Mathom. | The encrypted message is relayed by your browser's push service (Google FCM for Chrome/Android, Mozilla for Firefox, Apple for Safari/iOS). |
| **ntfy** | A notification in the [ntfy](https://ntfy.sh) app (Android/iOS/desktop), with a click-through link. | No, if you self-host ntfy on your LAN. |
| **Webhook** | A JSON `POST` to any URL, such as a Home Assistant automation or your own script. | Only if you point it outside. |

The message contains the Mathom's title and the first ~240 characters of its
newest summary (or the error message). It is written in the Mathom's summary
language (English, German or Spanish).

## Push notifications (PWA)

1. Open Mathom over **HTTPS** (push, like the share target, needs a secure
   context; see [the PWA guide](pwa.md)).
2. **iPhone/iPad:** add Mathom to the Home Screen first (Share → *Add to Home
   Screen*) and open it from there. iOS 16.4+ only offers Web Push to installed
   web apps.
3. Go to **Notifications → This device → Turn on for this device** and allow
   notifications when the browser asks.
4. Use **Send a test** to check that it works.

Repeat on every device you want notified. A device the push service reports as
gone (HTTP 404/410) is removed automatically.

### How it works

- On first use the backend generates a **VAPID** key pair (P-256) and stores it
  in the `app_settings` table. The browser subscribes with the public key.
- Each message is encrypted for that one device with **RFC 8291**
  (`aes128gcm`). The push service sees only ciphertext, the endpoint and the
  size. The VAPID JWT (**RFC 8292**) identifies the server to the push service.
- `frontend/public/sw.js` decrypts nothing itself (the browser does that). It
  shows the notification and, when you tap it, focuses or opens Mathom on the
  Mathom's page. It only ever navigates within Mathom's own origin.
- Subscriptions may only point at known push-service hosts
  (`MATHOM_WEB_PUSH_ALLOWED_HOSTS`), so a crafted subscription can't make the
  server POST somewhere else.
- Set `WEB_PUSH_CONTACT` (a `mailto:` or `https:` URL) so push services can
  reach the operator. Apple rejects placeholder contacts. If unset, Mathom uses
  `PUBLIC_BASE_URL` when it is `https://`.

## ntfy

1. Run ntfy yourself (for example `binwiederhier/ntfy` next to Mathom, or on
   TrueNAS as an app), or use a hosted server.
2. Choose a hard-to-guess topic, e.g. `https://ntfy.home.arpa/mathom-7f3k2`,
   and subscribe to it in the ntfy app.
3. Paste the topic URL into **Notifications → ntfy**. Add an access token if
   your server requires one; it is stored write-only.

Mathom uses ntfy's JSON publishing API (a `POST` to the server root with the
topic in the body), so titles in any language arrive intact.

## Webhook

Mathom sends `POST <your URL>` with `Content-Type: application/json`:

```json
{
  "event": "mathom.ready",
  "mathom_id": 42,
  "title": "“Garden plans” is ready",
  "body": "We agreed to plant the tomatoes next week…",
  "path": "/mathoms/42",
  "url": "https://mathom.example.com/mathoms/42",
  "sent_at": "2026-09-28T14:03:11.402+00:00"
}
```

- `event` is `mathom.ready`, `mathom.error`, or `test`.
- The `X-Mathom-Event` header repeats the event.
- With a signing secret, `X-Mathom-Signature: sha256=<hex>` is the HMAC-SHA256
  of the raw body. Verify it before trusting the payload.
- `url` is empty unless `PUBLIC_BASE_URL` is set.

## Links

Push notifications open the right page on their own. ntfy and webhook messages
need an absolute URL, which Mathom builds from `PUBLIC_BASE_URL` (or the public
base URL saved under the Sign-in or SMTP settings). Without one, ntfy messages
have no click-through, and webhooks get only `path`.

## Operator settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `NOTIFICATIONS_ENABLED` | `true` | `false` switches every channel off and hides the controls. |
| `WEB_PUSH_CONTACT` | *(empty)* | VAPID `sub` claim: `mailto:you@example.com` or an `https://` URL. |
| `MATHOM_WEB_PUSH_ALLOWED_HOSTS` | FCM, Mozilla, Apple, Windows | Push-service hosts (and their subdomains) subscriptions may use. |
| `MATHOM_NOTIFY_TIMEOUT_SECONDS` | `10` | Per-request timeout for every channel. |

## Security notes

- Delivery happens on a small background thread pool after the job completes.
  A slow or failing channel never delays or fails processing; failures are
  logged, and **Send a test** reports them per channel.
- ntfy and webhook URLs must be `http(s)`, can't carry credentials, and can't
  target loopback, link-local/metadata addresses, or the Ollama service. LAN
  addresses are allowed on purpose (self-hosted ntfy, Home Assistant). In a
  multi-user install every signed-in user can set these URLs for themselves.
  Use `NOTIFICATIONS_ENABLED=false` if that isn't acceptable.
- Redirects are not followed. Tokens and secrets are never returned by the API.
- Web Push is the one channel that always involves a third party: the
  browser's push service. The payload is end-to-end encrypted, but the service
  learns *that* a notification was sent to a device, and when.
