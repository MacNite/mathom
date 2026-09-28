# Automated audio collection — exploration

> Status: **proposal / research note.** Nothing here is implemented yet. It
> weighs the options for collecting voice messages into Mathom on its own
> (without the manual Share → Mathom step from [the PWA guide](pwa.md)) and for
> telling the user when the transcript is ready.

## The question

Could Mathom use an unofficial WhatsApp client library such as
[whatsmeow](https://github.com/tulir/whatsmeow) (Go) or
[whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js) (Node) to
pick up every audio message on its own, transcribe it, and then send a
notification with a link to the Mathom, either over WhatsApp or through the
Mathom PWA?

**Short answer:** yes, it is technically possible, and whatsmeow is the better
of the two libraries. But it conflicts with several of Mathom's own rules
(local-first, one custom image, no outbound calls) and with WhatsApp's Terms of
Service. The best route is in stages:

1. **Watch-folder ingest** (plus Syncthing on Android) handles most of the
   automation without touching WhatsApp's protocol.
2. **Notifications** are built once as a generic "Mathom ready" event with
   pluggable channels: PWA Web Push, self-hosted ntfy, or a generic webhook.
3. **An optional, opt-in WhatsApp companion** (whatsmeow sidecar in its own
   Compose overlay) for users who accept the trade-offs. It would default to a
   **"forward to yourself"** mode and send its notifications only to the
   user's own chat.

## Option A — Unofficial WhatsApp client (whatsmeow / whatsapp-web.js)

### How it works

Both libraries sign in as a **linked device** on the user's account, the same
way WhatsApp Web or Desktop does (you scan a QR code once). A linked device
receives every end-to-end-encrypted message addressed to the account. Media
messages carry a download URL and a media key, so the client can fetch and
decrypt the `.opus` voice note itself.

| | whatsmeow (Go) | whatsapp-web.js (Node) |
| --- | --- | --- |
| Mechanism | Speaks the multi-device protocol directly over a websocket | Drives real WhatsApp Web inside headless Chromium (Puppeteer) |
| Footprint | One static binary, ~20–40 MB RAM | Chromium plus Node, ~300–600 MB RAM |
| Stability | Mature; powers the `mautrix-whatsapp` Matrix bridge | Breaks whenever WhatsApp Web's frontend changes |
| Session store | SQLite (fits Mathom's volume model) | Browser profile directory |
| Media download | `client.Download(msg.GetAudioMessage())` | `msg.downloadMedia()` |
| Non-root / small image | Easy (distroless or alpine) | Harder (Chromium sandbox flags) |

[Baileys](https://github.com/WhiskeySockets/Baileys) (Node, websocket, no
browser) is the third common choice, with a similar footprint to whatsmeow.
**We recommend whatsmeow** because it is small, runs as a single binary, and
already stores its state in SQLite.

The official **WhatsApp Business Cloud API** is not an option. It runs on
Meta's cloud, needs a separate business number, and cannot read the user's
personal chats.

### Risks and conflicts (read before building)

- **Terms of Service.** WhatsApp forbids unofficial clients. A read-only
  linked device that only downloads media is low-profile, but it still risks
  having the number banned. Automated *sending* raises that risk a lot. Keep
  sending to the self-chat, at low volume, or don't send at all.
- **Local-first rule.** The companion has to connect out to WhatsApp's servers
  (`*.whatsapp.net`). That breaks the rule "no outbound calls except
  backend→Ollama". It has to be off by default, isolated in its own container,
  and listed in [the threat model](threat-model.md).
- **One-image rule.** A Go sidecar is a second custom image. It fits best as
  an optional overlay, `compose.whatsapp.yaml`, on the same pattern as
  `compose.gpu.yaml`. The core stack stays one image.
- **Other people's data.** Collecting "all audio" means processing voice
  messages from *other people*: storing them, transcribing them, and running
  them through an LLM. Under GDPR that is processing third-party personal
  data. In a household context it is probably covered by the household
  exemption, but in a work context it is not. The default should be an
  explicit per-chat opt-in, not "everything".
- **Session secrets.** The whatsmeow session store gives full access to the
  account (it can read *and send* as the user). It needs its own volume,
  `whatsapp-session`, owned by the sidecar's non-root user and never mounted
  into the app container. It should be covered by backups and documented as
  sensitive.
- **Linked-device expiry.** If the primary phone stays offline for about 14
  days, WhatsApp logs linked devices out. The sidecar has to surface that
  state ("re-scan QR") in its health status and in the UI.
- **Protocol churn.** WhatsApp changes its protocol. The whatsmeow version has
  to be pinned, and upgrades will sometimes be urgent.

### Collection modes (safest first)

1. **Self-chat / forward-to-me (default).** Only voice notes the user forwards
   into their own "Message yourself" chat are collected. The user stays in
   control, the ToS profile is minimal, and there is no third-party-consent
   problem beyond what the user chooses. In practice: long-press a voice note →
   Forward → *You*.
2. **Chat allowlist.** Every voice note in chosen chats is collected
   automatically (for example a family group, or one colleague who talks in
   voice notes). The allowlist lives in Mathom settings.
3. **Everything.** All incoming and outgoing voice notes. Only behind an
   explicit, warned opt-in.

Useful filters for all modes: voice notes only (`AudioMessage.PTT == true`)
versus any audio, a minimum duration, and whether to include the user's own
outgoing notes.

### Sketch

```
┌──────────────────────┐  websocket (E2E)  ┌────────────────────────┐
│  WhatsApp servers     │◀────────────────▶│  mathom-whatsapp       │
└──────────────────────┘                   │  (Go, whatsmeow)       │
                                           │  volume: whatsapp-     │
                                           │          session       │
                                           └───────────┬────────────┘
                              internal network, ingest token
                                                       ▼
                                   POST /api/ingest/audio (nginx → FastAPI)
                                                       │
                                     existing upload → job queue → pipeline
                                                       │  status = ready
                                                       ▼
                                   notifier ──▶ Web Push / ntfy / webhook
                                           └──▶ POST sidecar /notify → self-chat
```

Backend changes this would need, all additive in line with the schema rules:

- **Service tokens.** Auth today is cookie-session only (`deps.py`), so the
  sidecar needs a scoped bearer token (`api_tokens` table, hashed, scope
  `ingest`, tied to a user). This is also useful for scripts and Tasker.
- **`POST /api/ingest/audio`.** A thin wrapper over the existing upload
  validation (extension/content-type allowlist, `MAX_UPLOAD_MB`,
  server-generated filenames). It accepts metadata:
  `external_id` (the WhatsApp message ID), `source_app="WhatsApp"`,
  `speaker` (the sender's push name, which fills the existing `speaker`
  column), `chat_name` (a tag or collection), `recorded_at` (the message
  timestamp), and `template_slug`.
- **Dedup.** Add nullable columns `external_source` and `external_id` to
  `mathoms`, with a unique index on the pair. The sidecar retries safely and
  history sync never creates duplicates.
- **`recorded_at`.** Store the original message time. Today only
  `created_at` exists, so the timeline would show upload time, not when the
  message was sent.

## Option B — Watch-folder ingest (recommended first step)

Android WhatsApp already saves every voice note as a file:

```
/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes/<yyyyww>/PTT-20260722-WA0004.opus
```

[Syncthing](https://syncthing.net/) (Android app: Syncthing-Fork) can sync that
folder one way (*Send Only*) to a dataset on the TrueNAS box. Mathom watches a
mounted `inbox` directory and ingests any new file.

- **Fully local.** Traffic goes phone → NAS on the LAN. No WhatsApp protocol,
  no ToS problem, no new outbound calls.
- **Generic.** The same folder works for Telegram and Signal exports, call
  recorders, dictaphones, and meeting downloads. `source_app.py` already
  detects the app from `PTT-…-WA####` filenames.
- **Small change.** A polling scanner thread next to the existing worker (no
  inotify dependency; polling also works on NFS/SMB mounts). It debounces
  until the file size is stable, dedups on a content hash, then enqueues through
  the same upload path. It is configured with `MATHOM_INBOX_DIR`,
  `MATHOM_INBOX_POLL_SECONDS`, `MATHOM_INBOX_TEMPLATE`, and a policy of
  `keep | move | delete` after import.
- **Limits.** No sender or chat name, only the date from the filename. It does
  not work on iOS, because WhatsApp media is sandboxed there. By default it
  collects everything in the folder, so it has the same third-party-data point
  as Option A mode 3. Point Syncthing at a narrower folder if needed.
- **ToS-safe bulk import.** WhatsApp's own *Export chat → Include media*
  produces a `.zip` with the `.opus` files and a `_chat.txt`. An importer for
  that zip could restore sender names and timestamps by matching the
  `<attached: PTT-….opus>` lines. It is manual, but good for backfilling
  history.

## Notifications: "your Mathom is ready"

The pipeline already has one place where a recording finishes:
`_set_status(mathom_id, "ready")` in `backend/app/services/pipeline.py`. Add a
small `services/notify.py` that runs after it. It builds the link from
`MATHOM_PUBLIC_BASE_URL` (already a setting), for example
`https://mathom.example/mathoms/42`, adds a short title and a TL;DR line, and
sends to each channel the owning user has enabled. A failed notification is
logged and never fails the job. Notifications on `error` are also worth
sending ("couldn't transcribe").

| Channel | Local-first? | Works on | Notes |
| --- | --- | --- | --- |
| **PWA Web Push** | Mostly. The payload is end-to-end encrypted (RFC 8291), but delivery goes through the browser vendor's push service (FCM for Chrome, Mozilla autopush, Apple). | Android Chrome, desktop, iOS 16.4+ when installed to the Home Screen | Needs VAPID keys (generated once, stored in the DB), a `push_subscriptions` table, `push` + `notificationclick` handlers in `frontend/public/sw.js`, and the `pywebpush` dependency. HTTPS is already required for the PWA. Best UX because the tap opens the Mathom directly. |
| **ntfy (self-hosted)** / Gotify | Yes, fully, if self-hosted on the LAN | Android (ntfy app, UnifiedPush), iOS via ntfy.sh relay | A single HTTP POST with a `Click:` header set to the Mathom URL. Tiny to implement. |
| **Generic webhook** / Apprise | Depends on the target | Anything: Home Assistant, Matrix, email | One JSON POST covers Home Assistant automations and other custom setups. |
| **WhatsApp self-chat** | No (via the companion only) | Wherever WhatsApp is | Only if Option A is enabled. The backend POSTs to the sidecar, which sends the link to the user's own JID, never to the original chat. Replying in the original chat would message other people from an automated client, which is the highest ban risk and is surprising for everyone involved. |

**Recommendation:** start with **Web Push**, which makes the PWA itself the
notification surface, plus **ntfy/webhook** for fully local setups. Add
WhatsApp self-chat only as part of the optional companion.

## Suggested roadmap

| Phase | Scope | Rough size |
| --- | --- | --- |
| 1 | `notify.py` with the ready/error hook, ntfy and webhook channels, per-user settings UI | S |
| 2 | Web Push: VAPID, subscriptions API, service-worker handlers, "Enable notifications" toggle | M |
| 3 | Watch-folder inbox, plus a Syncthing guide in `docs/deployment.md` | M |
| 4 | Scoped API tokens and `POST /api/ingest/audio` with `external_id` dedup and `recorded_at` (also unlocks Tasker/iOS Shortcuts automation) | M |
| 5 | Optional `mathom-whatsapp` sidecar (whatsmeow) in `compose.whatsapp.yaml`: QR pairing page, self-chat mode first, allowlist later, self-chat notifications, threat-model update | L |

Phases 1–4 are useful on their own, keep every existing rule intact, and are
exactly the groundwork phase 5 needs. The later WhatsApp companion would then
be only a thin protocol adapter on top.

## Open questions for the maintainer

- Is an optional, off-by-default container with outbound WhatsApp traffic
  acceptable under the project's local-first promise, or should Option A stay
  a separate community add-on outside this repo?
- Which is the preferred notification default: Web Push (convenient, uses a
  vendor push relay) or ntfy (fully local, needs an extra app)?
- Is it worth backfilling via WhatsApp chat-export `.zip` import?
