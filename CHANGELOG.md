# Changelog

All notable changes to Mathom are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **Streaming summaries and chat render again.** Server-sent tokens are now
  emitted as JSON (`json.dumps`) instead of Python `repr()`, which the browser's
  `JSON.parse` rejected — the live typewriter view previously errored on the
  first token and content only appeared after a reload.
- **Deleting a summary now updates search.** The full-text index is refreshed on
  summary deletion, so removed summaries no longer surface as stale search hits.

### Security

- **Rate limiter can no longer be evaded with a spoofed `X-Forwarded-For`.** The
  per-client key is derived from the proxy-set `X-Real-IP` (falling back to the
  right-most forwarded hop), so a caller can no longer rotate the left-most,
  client-supplied header to mint a fresh bucket and bypass login throttling.
- **Prompt-template endpoints require authentication** when auth is enabled.
  Listing, creating, editing, and deleting templates previously accepted
  unauthenticated requests even though templates are global.
- **`must_change_password` is now enforced.** Accounts flagged for a mandatory
  password change (admin-created users and resets) are held at a change-password
  screen until they set a new password; the flag is exposed on the user API.
- **OIDC nonce binding.** The login is now bound to the ID token's `nonce`, so a
  replayed or injected token is rejected (`auth_error=invalid_nonce`).
- **Shorter default session lifetime** — 14 days instead of 30
  (`SESSION_TTL_HOURS`).
- **Content-Security-Policy and HSTS** headers at the proxy; the self-contained
  frontend is locked to `'self'`.
- **CycloneDX SBOM** generated and archived in CI (`security.yml`).
- **Loopback bind by default.** With authentication off (the default) the web UI
  now publishes on `127.0.0.1`; opt into LAN exposure with `MATHOM_BIND=0.0.0.0`.
- **Per-client rate limiting** on uploads, chat, summaries, search, and the
  login surface (in-process, no external store).
- **Content-based upload validation** with `ffprobe` (not just the extension),
  plus bounded FFmpeg execution (`-nostdin`, thread cap, timeout).
- **Safe user-facing errors** — pipeline failures no longer echo raw exception
  text (which could leak paths or upstream bodies); details are logged only.
- Pinned the Ollama image instead of tracking `latest`.

### Reliability

- **Durable background jobs**: replaced in-process `BackgroundTasks` with a
  `jobs` table drained by a single worker thread. Processing now survives a
  restart, failed runs retry with exponential backoff, and interrupted jobs are
  requeued (or the Mathom is flipped to a retryable `error`) at startup instead
  of hanging forever. The upload API is unchanged.
- SQLite `busy_timeout` so worker and request threads no longer race to a
  "database is locked" error.

### Documentation

- Added a [threat model](docs/threat-model.md); expanded backup and added
  disaster-recovery/restore guidance; documented the new secure defaults.

### Added

- Optional user management with **Authentik single sign-on** (OAuth2/OIDC),
  disabled by default so existing installs are unaffected. When enabled, each
  person signs in through Authentik and gets a private per-user mathom
  (Mathoms, chats, tags, collections are scoped per user). Roles are
  **Owner / Admin / User**; MFA/2FA is delegated to Authentik. The Owner can edit
  the Authentik connection in the UI, and pre-existing recordings are claimed by
  the Owner on first sign-in. Sessions use HttpOnly, SameSite=Lax, Secure
  cookies. See [docs/authentication.md](docs/authentication.md).
- Installable Progressive Web App with Android **Web Share Target** support:
  share a WhatsApp voice message (or any audio file) straight from the Android
  Share Sheet into your local mathom. A service worker receives the file
  and the app opens the upload dialog pre-filled, so the flow is
  *Share → Mathom → title/template → upload → transcribe → summarize*. Audio
  goes from your device to your own server only — no third parties.
- Language-aware AI output: summaries and follow-up chat now answer in the
  transcript's detected language instead of always English.
- Multilingual frontend (English, German, Spanish) with an in-app language
  switcher; the choice is remembered and defaults to the browser language.
- Initial Mathom stack: FastAPI backend, React + Vite + Tailwind frontend,
  nginx proxy, Ollama and faster-whisper integration, SQLite storage.
- mathom archive: upload → transcribe → summarize pipeline with status
  tracking, tags, favorites, archive, collections, timeline, and exports
  (Markdown / text / JSON).
- Full-text search (SQLite FTS5) with highlighted snippets.
- Follow-up AI chat grounded in each recording's transcript.
- 12 editable prompt templates seeded into SQLite.
- Docker Compose stack (CPU + NVIDIA GPU overlay), health checks, non-root
  containers, persistent volumes; TrueNAS SCALE deployment guide.
- CI: backend and frontend pipelines, compose validation, Docker builds,
  security scanning, GHCR release publishing.
