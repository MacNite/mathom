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
| `GET /mathoms/{id}`                  | Full detail: transcript, summaries, chat, tags, collections |
| `PATCH /mathoms/{id}`                | Update `title`, `favorite`, `archived`, `transcript` |
| `DELETE /mathoms/{id}`               | Delete row + audio file                    |
| `GET /mathoms/{id}/audio`            | Stream the original audio                  |
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

## Status lifecycle

`pending → transcribing → summarizing → ready`, or `error` (with
`error_message` set). Poll `GET /mathoms/{id}` while in flight.
