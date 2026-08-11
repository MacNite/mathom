# Changelog

All notable changes to Mathom are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet.

## [0.1.0] — 2026-08-11

First public release. Mathom turns the voice messages that interrupt your day
into private, searchable notes — transcribed and summarized entirely on your own
hardware. Nothing leaves your server.

Everything below is new, because this is where the archive opens.

### Added

#### The archive

- **Upload → transcribe → summarize pipeline.** Every recording becomes a
  *Mathom* and moves through `pending → transcribing → summarizing → ready`,
  with its audio, transcript, summaries, chat, tags, and metadata kept together.
- **Audio and video.** Common audio formats plus MP4/WebM video, whose audio
  track is transcribed with [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **Text and documents.** Paste text directly or import TXT, Markdown, PDF, and
  DOCX files.
- **12 editable prompt templates**, seeded into SQLite on first start and
  editable in the UI: TL;DR, General Summary, Meeting Minutes, Action Items,
  Email Draft, GitHub Issue, Jira Issue, CRM Entry, Calendar Events, Executive
  Brief, Customer Call, Technical Discussion.
- **Summaries you can steer** — generate several per Mathom, edit them by hand,
  regenerate with a different template, or delete the ones you don't want.
- **Streaming AI output.** Summaries and chat replies arrive token by token
  instead of after a long silence.
- **Follow-up chat** grounded in a recording's transcript, persisted per Mathom.
- **Full-text search** (SQLite FTS5) across titles, transcripts, summaries, and
  tags, with highlighted snippets.
- **Tags with colors**, favorites, an archive, collections, a timeline view, and
  filtering by source app — plus a speaker field and source-app hint at upload.
- **Exports** per Mathom as Markdown, plain text, or JSON.

#### Getting recordings in

- **Installable Progressive Web App** with Android **Web Share Target** support:
  share a WhatsApp voice message — or any supported audio, video, or document —
  straight from the share sheet into your own archive. The flow is
  *Share → Mathom → title/template → upload → transcribe → summarize*, and the
  file goes from your device to your server only. There is deliberately no app
  store build; see [docs/pwa.md](docs/pwa.md).
- **iOS-aware PWA layout** with safe-area handling and outbound sharing.

#### Language

- **Language-aware AI output.** Summaries and chat answer in the transcript's
  detected language rather than always English.
- **Multilingual interface** — English, German, and Spanish, with an in-app
  switcher that defaults to your browser language and remembers your choice.

#### Optional, off by default

- **Local video visual analysis** (`MATHOM_VISION_ENABLED`). Samples still
  frames, sends only those frames to a local vision-capable Ollama model, and
  stores timestamped observations separately from the spoken transcript. No
  model is ever downloaded automatically; `/api/health` reports whether the
  configured model is installed and vision-capable.
- **Speaker diarization** (`MATHOM_DIARIZATION_ENABLED`) via a locally
  provisioned [pyannote.audio](https://github.com/pyannote/pyannote-audio)
  pipeline and the backend's `diarization` extra. Mathom downloads nothing and
  sends audio nowhere.
- **User management and Authentik SSO.** Enable `AUTH_ENABLED` for local
  accounts with first-start onboarding, or connect
  [Authentik](https://goauthentik.io/) (OAuth2/OIDC) for single sign-on with
  MFA delegated to your identity provider. Roles are **Owner / Admin / User**,
  each person gets a private archive (Mathoms, chats, tags, and collections are
  scoped per user), the Owner can edit the connection in the UI, and recordings
  created before sign-in is enabled are claimed by the Owner. See
  [docs/authentication.md](docs/authentication.md).
- **SMTP invitations** — invite people by email, with branded invitation mail
  and revocable invitations.

#### Running it

- **One Docker Compose stack**: a single `mathom` image (React frontend,
  FastAPI backend, and nginx under supervisord) plus the stock, pinned Ollama
  image. Only Mathom publishes a port; Ollama stays on the internal network.
- **NVIDIA GPU overlay** (`compose.gpu.yaml`), health checks on every service,
  non-root containers, persistent named volumes, and a TrueNAS SCALE
  deployment path.
- **Published images** on GHCR (`ghcr.io/macnite/mathom`) for tagged releases.
- **Makefile targets** for the common operations: `up`, `up-gpu`, `models`,
  `backup`, `test`, `lint`, `validate`.
- **Landing site** with an interactive static demo of the app, deployed to
  GitHub Pages.

### Security

Mathom ships locked down by default, so that a fresh install is safe before you
have configured anything.

- **Loopback bind by default.** With authentication off (the default) the web UI
  publishes on `127.0.0.1` and is reachable only from the host. Opt into LAN
  exposure with `MATHOM_BIND=0.0.0.0` — behind a VPN or an authenticating
  reverse proxy, or with SSO enabled.
- **No telemetry, no cloud.** The only outbound calls are backend→Ollama on the
  internal network, and backend→Authentik when you enable SSO.
- **Content-based upload validation** with `ffprobe` — not just the file
  extension — plus size caps, server-generated filenames, and bounded FFmpeg
  execution (`-nostdin`, thread cap, timeout).
- **Per-client rate limiting** on uploads, chat, summaries, search, and the
  login surface, keyed off the proxy-set client address so a spoofed
  `X-Forwarded-For` cannot mint a fresh bucket. In-process; no external store.
- **Content-Security-Policy and HSTS** at the proxy; the self-contained
  frontend is locked to `'self'`.
- **Session and account handling**: HttpOnly, SameSite=Lax, Secure cookies; a
  14-day default session lifetime (`SESSION_TTL_HOURS`); enforced
  `must_change_password` for admin-created and reset accounts; OIDC logins bound
  to the ID token `nonce` so a replayed token is rejected.
- **Authenticated prompt-template endpoints** when auth is enabled.
- **Safe user-facing errors** — pipeline failures never echo raw exception text;
  details go to the logs only.
- **CI supply-chain checks**: pip-audit, npm audit, Trivy filesystem scan, and a
  CycloneDX SBOM archived on every run.

### Reliability

- **Durable background jobs.** A `jobs` table drained by a single worker thread
  replaces in-process background tasks: processing survives a restart, failed
  runs retry with exponential backoff, and interrupted jobs are requeued (or
  flipped to a retryable `error`) at startup instead of hanging forever.
- **Queue backpressure** — new uploads receive `503` with `Retry-After` once
  `MAX_QUEUED_JOBS` recordings are already waiting.
- SQLite `busy_timeout`, so the worker and request threads no longer race into
  "database is locked".
- Stale error state is cleared after a successful run, and failed visual
  inspections recover instead of pinning a Mathom to `error`.

### Documentation

- [Architecture](docs/architecture.md), [Deployment incl. TrueNAS
  SCALE](docs/deployment.md), [Threat model](docs/threat-model.md),
  [Authentication](docs/authentication.md), [PWA & Android Share
  Target](docs/pwa.md), and an [API overview](docs/api.md).
- Backup, restore, and disaster-recovery guidance; the exposure warning to read
  before putting Mathom on a network.

[Unreleased]: https://github.com/MacNite/mathom/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MacNite/mathom/releases/tag/v0.1.0
