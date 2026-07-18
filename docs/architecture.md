# Architecture

## Services

```
┌──────────┐      ┌──────────────────┐      ┌──────────────────┐
│ Browser   │─────▶│ proxy (nginx)    │─────▶│ backend (FastAPI)│
│ React UI  │ :8080│ static frontend  │ /api │ Python 3.11      │
└──────────┘      │ + reverse proxy  │      └───────┬──────────┘
                   └──────────────────┘              │
                                          ┌──────────┼──────────────┐
                                          ▼          ▼              ▼
                                    ┌─────────┐ ┌──────────┐ ┌────────────┐
                                    │ SQLite   │ │ audio    │ │ Ollama     │
                                    │ mathom.db│ │ files    │ │ (internal) │
                                    └─────────┘ └──────────┘ └────────────┘
```

- **proxy** — nginxinc/nginx-unprivileged. The only service with a published
  port. Serves the built React app and proxies `/api/*` to the backend with
  long timeouts (transcription can be slow) and a large `client_max_body_size`
  for uploads.
- **backend** — FastAPI + SQLAlchemy 2.0 + SQLite. Owns all state. Runs
  faster-whisper in-process (background tasks) and talks to Ollama over HTTP.
- **ollama** — serves the LLM. **No published ports** — reachable only on the
  internal Compose network.

## The Mathom lifecycle

1. `POST /api/mathoms` stores the audio under a server-generated name and
   creates a row with status `pending`.
2. A FastAPI background task runs the pipeline
   (`backend/app/services/pipeline.py`):
   - `transcribing` — FFmpeg normalizes to 16 kHz mono WAV, ffprobe reads
     the duration, faster-whisper produces transcript + language.
   - `summarizing` — the chosen prompt template is rendered
     (`{transcript}` placeholder) and sent to Ollama.
   - `ready` — or `error`, with the message stored on the row.
3. The frontend polls while a Mathom is in flight and renders live status.

## Data model

SQLite tables (SQLAlchemy models in `backend/app/models.py`):

| Table                | Purpose                                       |
| -------------------- | --------------------------------------------- |
| `mathoms`            | One row per recording: audio path, transcript, status, flags |
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
