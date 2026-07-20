# Mathom

> **Turn annoying voice messages into private, useful notes**

Mathom turns the voice notes that interrupt your day — from WhatsApp, Telegram,
recorders, and web meetings — into useful, private notes. It transcribes recordings
with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), summarizes
them with [Ollama](https://ollama.com), and shelves every recording as a
**Mathom** in your searchable local archive. Your data never leaves your own
server.

*In Tolkien's Shire, a "mathom" is anything hobbits have no immediate use for
but are unwilling to throw away — kept safe rather than tossed out. Yours go
here.*

## Features

- 🎙️ **Voice-message transcription** — bring in WhatsApp, Telegram, recorder, or
  web-meeting audio; faster-whisper and FFmpeg handle common formats
- ✨ **Useful summaries** — 12 editable prompt templates: TL;DR, Meeting Minutes,
  Action Items, Email Draft, GitHub/Jira Issue, CRM Entry, Calendar Events,
  Executive Brief, and more
- 💬 **Follow-up chat** — ask questions about any recording, grounded in its
  transcript
- 🔍 **Full-text search** — SQLite FTS5 across titles, transcripts, and
  summaries, with highlighted snippets
- 🏷️ **Tags, favorites, collections, archive, timeline** — a real archive, not
  a junk drawer
- 📤 **Exports** — Markdown, plain text, or JSON per Mathom
- 👥 **Optional multi-user + SSO** — off by default; enable
  [Authentik](https://goauthentik.io/) single sign-on for private per-user
  archives with Admin/User roles and Authentik-managed MFA
  ([docs](docs/authentication.md))
- 📱 **Installable PWA share target** — share audio directly from supported apps
  into Mathom after installing it on your phone
- 🏠 **Privacy first** — no cloud, no telemetry; Ollama is never exposed
  publicly
- 🚫 **No Play Store app** — installation as a PWA is intentional: it avoids a
  third-party app-store distribution path and keeps your connection direct to your server.
- 🐳 **One Docker Compose stack** — CPU by default, optional NVIDIA GPU
  overlay, TrueNAS SCALE compatible

## Quick Start

Requirements: Docker with Compose v2. Optional: NVIDIA Container Toolkit for
GPU acceleration.

```bash
git clone https://github.com/MacNite/mathom.git
cd mathom
cp .env.example .env      # adjust if you like — defaults work
make up                   # CPU stack
make models               # pull the Ollama model (first run only)
```

Open **http://localhost:8080** and bring your first recording home. For phone
voice messages, install Mathom as a PWA from your browser; it can then appear in
the share sheet of supported apps. There is deliberately no Play Store app — see
[the PWA guide](docs/pwa.md).

GPU users: `make up-gpu` instead of `make up`.

## How It Works

```
Browser ──▶ mathom container ──▶ Ollama (internal only)
             nginx + FastAPI
             + React frontend
             SQLite + audio (persistent volume)
```

Mathom ships as a **single image** (React frontend, FastAPI backend, and nginx
in one container, run together by supervisord) plus the stock Ollama image.
Only the mathom container publishes a port; Ollama stays on the internal
network.

Each upload (or audio shared from the installed PWA) becomes a Mathom and
moves through
`pending → transcribing → summarizing → ready`. Everything about it — audio,
transcript, summaries, chat, tags, metadata — is stored locally in SQLite and
a persistent volume.

## Security & privacy

Mathom is local-first by design, and ships with safe defaults:

- **No login by default → loopback-only.** With authentication off (the
  default) the web UI binds to `127.0.0.1`, so a fresh install is reachable
  only from the host. Set `MATHOM_BIND=0.0.0.0` for LAN access — only behind a
  VPN / authenticating reverse proxy, or with SSO enabled.
- **No telemetry, no cloud.** The only outbound calls are backend→Ollama on the
  internal network, and backend→Authentik **when you enable SSO**. Ollama is
  never published.
- **Uploads are validated** by extension *and* content (`ffprobe`), size-capped,
  and stored under server-generated names; FFmpeg runs sandboxed with fixed
  arguments and timeouts.
- **Rate limiting** protects uploads, chat, search, and the login surface.
- **Optional Authentik SSO** adds per-user archives, RBAC, and MFA.

Before exposing Mathom beyond your own machine, read the
[deployment exposure warning](docs/deployment.md#exposure-warning) and the
[threat model](docs/threat-model.md).

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

| Variable               | Default    | Purpose                                |
| ---------------------- | ---------- | -------------------------------------- |
| `MATHOM_PORT`          | `8080`     | Host port for the web UI               |
| `OLLAMA_MODEL`         | `llama3.2` | Model for summaries and chat           |
| `OLLAMA_BASE_URL`      | `http://ollama:11434` | Ollama endpoint; can be another private stack |
| `OLLAMA_TIMEOUT_SECONDS` | `300` | Deadline for each Ollama request       |
| `WHISPER_MODEL`        | `small`    | faster-whisper model size              |
| `WHISPER_DEVICE`       | `cpu`      | `cpu` or `cuda`                        |
| `WHISPER_COMPUTE_TYPE` | `int8`     | `int8` (CPU) / `float16` (GPU)         |
| `MAX_UPLOAD_MB`        | `200`      | Upload size limit per recording        |
| `MAX_QUEUED_JOBS`      | `25`       | Maximum recordings waiting to process  |
| `CHAT_CONCURRENCY`     | `1`        | Simultaneous interactive Ollama chats  |

## Documentation

- [Architecture](docs/architecture.md)
- [Deployment (including TrueNAS SCALE)](docs/deployment.md)
- [Threat model](docs/threat-model.md)
- [Authentication & user management (Authentik SSO)](docs/authentication.md)
- [PWA & Android Share Target](docs/pwa.md)
- [API overview](docs/api.md)
- [Contributing](CONTRIBUTING.md) · [Security policy](SECURITY.md) ·
  [Changelog](CHANGELOG.md)
- [CLAUDE.md](CLAUDE.md) — project standards and conventions

## Development

```bash
make test       # backend pytest + frontend vitest
make lint       # ruff, mypy, eslint, tsc
./scripts/dev.sh  # run backend :8000 + frontend :5173 without Docker
```

## License

[MIT](LICENSE)
