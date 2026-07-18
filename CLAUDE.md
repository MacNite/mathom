# CLAUDE.md — Mathom Project Guide

> Mathom — Your Local AI Memory House.
> This file is the source of truth for how the project is structured, built,
> tested, and shipped. Read it before making changes.

## What Mathom Is

Mathom is a fully local, self-hosted AI memory house. It transcribes voice
recordings with faster-whisper, summarizes them with Ollama, and stores each
recording as a **Mathom** — audio, transcript, summaries, AI outputs, tags,
follow-up chat — in a searchable archive called the **Mathom-house**.
Everything runs on the user's own hardware (TrueNAS SCALE / any Docker host).
No cloud services, ever.

## Architecture

```
┌────────────┐     ┌─────────────────────┐     ┌───────────────┐
│  Browser    │────▶│  proxy (nginx)      │────▶│  backend      │
│  (React UI) │     │  serves frontend,   │     │  (FastAPI)    │
└────────────┘     │  proxies /api       │     └──────┬────────┘
                    └─────────────────────┘            │
                                              ┌────────┴────────┐
                                              │                 │
                                        ┌─────▼─────┐   ┌───────▼───────┐
                                        │  SQLite    │   │  Ollama       │
                                        │  + files   │   │  (internal    │
                                        │  volume    │   │   only)       │
                                        └───────────┘   └───────────────┘
```

- **backend/** — FastAPI (Python 3.11+). Owns the SQLite database, audio file
  storage, transcription (faster-whisper), summarization and chat (Ollama via
  HTTP), prompt templates, search, tags, collections, exports.
- **frontend/** — React 18 + Vite + TypeScript + Tailwind CSS. Talks only to
  `/api/*`. Built to static assets and served by the proxy.
- **proxy/** — nginx. The single public entry point. Serves the frontend
  build, reverse-proxies `/api` to the backend. Ollama is never exposed.
- **prompt-templates/** — seed JSON templates loaded into SQLite on first
  startup. Users edit templates in the UI; the DB copy is authoritative.
- **docs/** — architecture, deployment (incl. TrueNAS SCALE), API docs.
- **scripts/** — operational helpers (setup, backup, model pull).
- **.github/workflows/** — CI/CD.

### Data model (SQLite)

Core tables: `mathoms`, `summaries`, `chat_messages`, `tags`, `mathom_tags`,
`collections`, `collection_mathoms`, `prompt_templates`. Schema lives in
`backend/app/models.py` (SQLAlchemy). Migrations are handled by
`Base.metadata.create_all` plus additive migration helpers in
`backend/app/db.py` — keep schema changes additive; destructive changes
require an explicit migration script in `scripts/`.

### Key backend flows

1. **Upload** → audio saved under `DATA_DIR/audio/`, Mathom row created,
   background task transcribes (faster-whisper) then summarizes (Ollama with
   the chosen prompt template), status transitions
   `pending → transcribing → summarizing → ready` (or `error`).
2. **Follow-up chat** → chat history + transcript context sent to Ollama;
   messages persisted per Mathom.
3. **Search** → SQLite FTS5 over transcript + summaries + title + tags.

## Coding Standards

### Python (backend)
- Python 3.11+, type hints everywhere; `mypy` must pass (config in
  `backend/pyproject.toml`).
- Lint/format with `ruff` (lint + format). Line length 100.
- FastAPI routers per domain in `backend/app/routers/`; business logic in
  `backend/app/services/`; no DB access from routers except via
  dependency-injected sessions.
- Never block the event loop: transcription/summarization run in worker
  threads or background tasks.
- All external calls (Ollama) go through `services/ollama.py` with timeouts.

### TypeScript (frontend)
- Strict TypeScript (`"strict": true`); `tsc --noEmit` must pass.
- ESLint with the project config; Prettier-compatible formatting.
- Components in `src/components/`, pages in `src/pages/`, API client in
  `src/lib/api.ts` (the only place `fetch` is called).
- Tailwind for all styling; design tokens in `tailwind.config.js`. No inline
  hex colors — use the theme palette.

### General
- No secrets in code. Configuration via environment variables only; document
  every variable in `.env.example`.
- Keep functions small; prefer pure functions in services.
- User-facing strings: warm, calm, minimal tone (see Branding below).

## Docker Rules

- One Compose stack: `compose.yaml` (CPU). GPU users add
  `compose.gpu.yaml` as an overlay: `docker compose -f compose.yaml -f
  compose.gpu.yaml up`.
- All containers run as **non-root** users.
- Every service defines a **healthcheck**.
- Persistent named volumes for: SQLite + audio (`mathom-data`), Ollama models
  (`ollama-models`), whisper models (`whisper-models`).
- **Ollama must never publish a host port.** It is reachable only on the
  internal Compose network. Only the proxy publishes a port.
- Images are multi-stage, pinned base images, `.dockerignore` kept current.
- TrueNAS SCALE: stack must work with host-path volumes substituted for named
  volumes; document in `docs/deployment.md`.

## Security

- Local-first: no telemetry, no outbound calls except backend→Ollama on the
  internal network.
- The proxy is the only exposed service. Backend binds to the Compose network
  only.
- Validate all uploads: extension + content-type allowlist, size limit
  (`MAX_UPLOAD_MB`), filenames are never trusted (server-generated names).
- SQL only via SQLAlchemy parameterized queries; FTS queries sanitized.
- No `eval`, no shelling out with user input; FFmpeg/whisper invoked with
  fixed argument lists.
- Dependencies scanned in CI (`security.yml`: pip-audit, npm audit, Trivy).
- Report vulnerabilities per `SECURITY.md`.

## Testing

- Backend: `pytest` in `backend/tests/`. External services (whisper, Ollama)
  are always mocked; tests must run with no network and no models. Target:
  every router has tests; services have unit tests.
- Frontend: `vitest` + React Testing Library in `frontend/src/**/*.test.tsx`.
- Run everything locally with `make test`.
- CI must be green before merge; no skipped tests without a linked issue.

## CI Rules (.github/workflows/)

| Workflow                 | Runs on            | Does                                    |
| ------------------------ | ------------------ | --------------------------------------- |
| `backend-ci.yml`         | PR + main          | ruff, mypy, pytest                      |
| `frontend-ci.yml`        | PR + main          | eslint, tsc, vitest, vite build         |
| `compose-validation.yml` | PR + main          | `docker compose config` for both stacks |
| `docker-build.yml`       | PR + main          | build backend + frontend/proxy images   |
| `security.yml`           | PR + main + weekly | pip-audit, npm audit, Trivy FS scan     |
| `release-images.yml`     | tags `v*`          | build + push GHCR images                |

Workflows pin action versions, use least-privilege `permissions:`, and cache
dependencies.

## Branch Strategy

- `main` is protected and always releasable.
- Work happens on short-lived branches: `feat/…`, `fix/…`, `docs/…`,
  `chore/…`.
- All changes land via Pull Request with green CI. No direct pushes to main.
- Releases are tags `vX.Y.Z` on main; `release-images.yml` publishes images.

## Commit Conventions

Conventional Commits:

```
<type>(<scope>): <summary>

feat(backend): add FTS5 search across transcripts
fix(frontend): keep chat scroll pinned to bottom
docs: describe TrueNAS SCALE deployment
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`,
`build`. Imperative mood, ≤72-char summary, body explains *why* when
non-obvious.

## Deployment Guidance

- **Quick start:** `cp .env.example .env`, `make up` (CPU) or `make up-gpu`.
- First run pulls the Ollama model defined by `OLLAMA_MODEL` via
  `scripts/pull-model.sh` (or `make models`).
- **TrueNAS SCALE:** install via *Apps → Custom App / Docker Compose*, point
  volumes at datasets, see `docs/deployment.md`.
- Backups: `scripts/backup.sh` snapshots the SQLite DB (with `sqlite3
  .backup`) and the audio directory.
- Upgrades: pull new images, `docker compose up -d`; schema migrations are
  additive and run automatically at backend startup.

## Branding

- Name: **Mathom** — tagline: *Your Local AI Memory House*.
- Voice & design: warm, calm, minimal, cozy, professional. Inspired by
  libraries, maps, notebooks, archive shelves, rounded doorways.
- Rounded corners, parchment/amber/moss palette (defined in Tailwind theme),
  generous whitespace, serif display + sans body.
- No copyrighted Tolkien artwork or trademarked names beyond the generic word
  "mathom". The app should feel like a trusted local archive for
  conversations and memories.
