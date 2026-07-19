# Architecture

## Services

Mathom runs as **two containers**: the single `mathom` image (frontend +
backend + nginx) and stock Ollama. Inside the `mathom` container, nginx and the
FastAPI backend run side by side under supervisord.

```
┌──────────┐      ┌───────────────────────────────────────┐      ┌────────────┐
│ Browser   │────▶│ mathom container            :8080     │      │ Ollama     │
│ React UI  │      │  nginx ──/api──▶ FastAPI (127.0.0.1)  │─────▶│ (internal) │
└──────────┘      │  + built React app   (supervisord)    │      └────────────┘
                   └───────────────────┬───────────────────┘
                                        │
                              ┌─────────┼──────────┐
                              ▼         ▼
                        ┌─────────┐ ┌──────────┐
                        │ SQLite   │ │ audio    │
                        │ mathom.db│ │ files    │
                        └─────────┘ └──────────┘
```

- **mathom** — one image, built from the repository-root `Dockerfile`, running
  three things in one non-root container via supervisord:
  - **nginx** (from `docker/nginx.conf`) — the only published port (`:8080`).
    Serves the built React app and proxies `/api/*` to the backend on
    `127.0.0.1:8000` with long timeouts (transcription can be slow) and a large
    `client_max_body_size` for uploads.
  - **backend** — FastAPI + SQLAlchemy 2.0 + SQLite (uvicorn, loopback-only).
    Owns all state. Runs faster-whisper in-process via a **durable job queue**
    (a `jobs` table drained by one worker thread) and talks to Ollama over HTTP.
- **ollama** — serves the LLM. **No published ports** — reachable only on the
  internal Compose network.

## The Mathom lifecycle

1. `POST /api/mathoms` stores the audio under a server-generated name, creates
   a row with status `pending`, and **enqueues a durable job** (`jobs` table).
2. The worker thread (`backend/app/services/worker.py`) claims the job and runs
   the pipeline (`backend/app/services/pipeline.py`):
   - `transcribing` — the upload is validated with ffprobe (a real audio stream
     is required), FFmpeg normalizes to 16 kHz mono WAV, ffprobe reads the
     duration, faster-whisper produces transcript + language.
   - `summarizing` — the chosen prompt template is rendered
     (`{transcript}` placeholder) and sent to Ollama.
   - `ready` — or `error`, with a safe, generic message stored on the row.
3. On failure the job is retried with exponential backoff up to `max_attempts`;
   the Mathom is only marked `error` once retries are exhausted.
4. **Restart recovery:** at startup any job left `running` is requeued, and any
   Mathom in an in-flight status that no live job owns is flipped to a retryable
   `error`. Nothing is lost or stuck when the container restarts.
5. The frontend polls while a Mathom is in flight and renders live status.

## Data model

SQLite tables (SQLAlchemy models in `backend/app/models.py`):

| Table                | Purpose                                       |
| -------------------- | --------------------------------------------- |
| `mathoms`            | One row per recording: audio path, transcript, status, flags |
| `jobs`               | Durable background work queue (one row per pipeline run) |
| `summaries`          | AI outputs, one per (mathom, template run)    |
| `chat_messages`      | Follow-up conversation per mathom             |
| `tags`, `mathom_tags`| Free-form labels                              |
| `collections`, `collection_mathoms` | Named shelves of mathoms       |
| `prompt_templates`   | Editable templates (seeded from `prompt-templates/`) |
| `mathom_fts`         | FTS5 index: title + transcript + summaries    |

`mathom_fts` uses the mathom id as its rowid and is refreshed by
`app.db.refresh_fts` whenever title, transcript, or summaries change.

## Search

User input is tokenized and each token quoted (`"term"*`) before being passed
to FTS5 — FTS query syntax from user input is never interpreted. Results are
ranked with FTS5's default BM25 and returned with `snippet()` highlights,
rendered safely (no raw HTML injection) in the frontend.

## Prompt templates

Seed JSON files live in `prompt-templates/`. On startup the backend inserts
any missing slug into SQLite (insert-only, so user edits win). The UI edits
the SQLite copies; every template must contain the `{transcript}`
placeholder.

## Frontend

React 18 + Vite + TypeScript + Tailwind. All backend access goes through
`src/lib/api.ts`. Pages: Library (list, filters, live search), Mathom detail
(player, transcript, summaries, tags, collections, exports, chat), Templates,
Collections, Timeline. The design language is warm and archival: parchment
palette, serif display type, rounded "doorway" cards.
