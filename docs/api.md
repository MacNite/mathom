# API Overview

The backend serves an interactive OpenAPI UI at `/docs` (through the proxy:
`http://<host>:8080/api` is proxied, so use the backend directly in dev:
`http://localhost:8000/docs`).

All routes are prefixed with `/api`.

## Mathoms

| Method & path                        | Purpose                                    |
| ------------------------------------ | ------------------------------------------ |
| `GET /mathoms`                       | List (filters: `favorite`, `archived`, `tag`, `status`, paging) |
| `POST /mathoms`                      | Upload (multipart: `file`, `title?`, `template_slug?`) — starts the pipeline |
| `POST /mathoms/text`                 | Queue pasted text (JSON: `text`, `title?`, template options) |
| `POST /mathoms/documents`            | Queue TXT, MD, PDF, or DOCX extraction |
| `GET /mathoms/{id}`                  | Full detail: transcript, summaries, chat, tags, collections |
| `PATCH /mathoms/{id}`                | Update `title`, `favorite`, `archived`, `transcript` |
| `DELETE /mathoms/{id}`               | Delete row + audio file                    |
| `GET /mathoms/{id}/audio`            | Stream the original audio                  |
| `GET /mathoms/{id}/source`           | Download the original media or document source |
| `POST /mathoms/{id}/visual-analysis` | Queue local visual analysis for a retained video |
| `POST /mathoms/{id}/summaries`       | Generate another summary (`template_slug`) |
| `POST /mathoms/{id}/tags`            | Add tag by name                            |
| `DELETE /mathoms/{id}/tags/{tagId}`  | Remove tag                                 |
| `GET /mathoms/{id}/export?format=md` | Export `md`, `txt`, or `json`              |

## Chat

| Method & path                   | Purpose                                  |
| ------------------------------- | ---------------------------------------- |
| `GET /mathoms/{id}/chat`        | Conversation history                     |
| `POST /mathoms/{id}/chat`       | Send a message; returns updated history  |
| `DELETE /mathoms/{id}/chat`     | Clear the conversation                   |

## Templates

`GET/POST /templates`, `GET/PUT/DELETE /templates/{id}`. Prompts must contain
the `{transcript}` placeholder. Built-in templates are editable; deleting one
does not resurrect it (seeding is insert-only).

## Collections

`GET/POST /collections`, `GET/PUT/DELETE /collections/{id}`,
`POST/DELETE /collections/{id}/mathoms/{mathomId}`.

## Search & discovery

| Method & path        | Purpose                                            |
| -------------------- | -------------------------------------------------- |
| `GET /search?q=`     | FTS5 search; returns hits with `<mark>` snippets   |
| `GET /tags`          | All tags                                           |
| `GET /timeline`      | Mathom counts bucketed by month                    |
| `GET /health`        | Status, version, Ollama reachability               |

## Notifications

Per user (or the single local user when auth is off). See
[notifications.md](notifications.md).

| Method & path                                | Purpose                                              |
| -------------------------------------------- | ---------------------------------------------------- |
| `GET /notifications/settings`                | Preferences, channel URLs, `*_set` flags, device count |
| `PUT /notifications/settings`                | Partial update; blank token/secret keeps the stored one |
| `POST /notifications/test`                   | Send a test on every channel; per-channel results    |
| `GET /notifications/webpush/key`             | VAPID public key for `pushManager.subscribe`         |
| `POST /notifications/webpush/subscriptions`  | Register this device (`PushSubscription.toJSON()`)   |
| `POST /notifications/webpush/unsubscribe`    | Forget a device by `endpoint`                        |

## Automated ingest

See [ingest.md](ingest.md).

| Method & path                          | Purpose                                                   |
| -------------------------------------- | --------------------------------------------------------- |
| `GET /tokens`                          | Your API tokens (never the secret)                        |
| `POST /tokens`                         | Create `{name, expires_in_days?}`; returns `token` once   |
| `DELETE /tokens/{id}`                  | Revoke a token                                            |
| `POST /ingest/audio`                   | Bearer-token multipart upload; `200` + `X-Mathom-Duplicate` on a resend |
| `POST /ingest/audio/raw?filename=`     | Same, with the file as the raw body                       |
| `GET /ingest/inbox`                    | Watched-folder status (admins when auth is on)            |
| `POST /ingest/inbox/scan`              | Scan the watched folder now                               |
| `GET /ingest/inbox/me`                 | Your folder name, path, and import count                  |
| `PUT /ingest/inbox/me`                 | Rename your folder `{inbox_name}` (sign-in mode)          |

## Authentication (optional)

Active only when `MATHOM_AUTH_ENABLED=true`; otherwise these behave as noted and
all other endpoints are open. See [authentication.md](authentication.md).

| Method & path              | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| `GET /auth/status`         | Whether auth is enabled/configured and the current user (public) |
| `GET /auth/login?next=`    | Redirect to Authentik to sign in                               |
| `GET /auth/callback`       | OAuth redirect target; sets the session cookie                 |
| `POST /auth/login/local`   | Email + password sign-in; `403` while password sign-in is off  |
| `POST /auth/logout`        | End the current session                                        |
| `POST /users`              | Create a standard user; `password` optional (Authentik-only account), refused while password sign-in is off *(Admin)* |
| `GET /users`               | List users *(Admin/Owner)*                                     |
| `PATCH /users/{id}`        | Change `role` *(Owner)* or `is_active` *(Admin for users)*     |
| `DELETE /users/{id}`       | Remove a user *(Owner)*                                        |
| `GET /invitations`          | List invitation status *(Admin)*                              |
| `POST /invitations`         | Send a password-setup invitation; `403` while password sign-in is off *(Admin)* |
| `POST /invitations/{id}/revoke` | Revoke a pending invitation *(Admin)*                    |
| `DELETE /invitations/{id}`  | Delete a revoked, expired, or accepted invitation *(Admin)*    |
| `POST /invitations/accept`  | Accept invitation and set local password *(public)*            |
| `GET /settings/smtp`        | Read SMTP setup, password masked *(Admin)*                     |
| `PUT /settings/smtp`        | Update SMTP setup *(Admin)*                                    |
| `GET /settings/authentik`  | Read Authentik connection settings, secret masked *(Owner)*    |
| `PUT /settings/authentik`  | Update Authentik connection settings and `local_login_enabled` (password sign-in switch; `409` if that would risk a lockout) *(Owner)* |

When auth is enabled, all Mathom/chat/collection/search endpoints require a
session cookie (`401` otherwise) and return only the caller's own rows.

## Status lifecycle

Media upload accepts `analyze_visuals=false` as a multipart boolean. The response includes stream
capabilities and vision fields (`vision_status`, `vision_model`, `visual_summary`, timestamped
`visual_observations`, and a safe error message). A video-only upload requires this option and
global visual analysis to be enabled. `POST /mathoms/{id}/visual-analysis` is authenticated,
ownership-scoped, durable, and refuses duplicate processing; it preserves existing summaries.

`pending → transcribing → summarizing → ready`, or `error` (with
`error_message` set). Poll `GET /mathoms/{id}` while in flight.

### Timestamped transcripts and subtitles

Mathom detail responses include `segments`, each with `start`, `end`, `text`, and an optional
`speaker`. Use `GET /api/mathoms/{id}/export?format=srt` or `format=vtt` for local subtitle
exports. `PATCH /api/mathoms/{id}` accepts `transcript`, and `PATCH
/api/mathoms/{id}/summaries/{summary_id}` accepts a hand-corrected `content`.

`POST /api/mathoms/{id}/summaries/stream` and `POST /api/mathoms/{id}/chat/stream` return
server-sent events (`data` token events followed by `done`) while persisting the completed result.
