# Threat Model

This document describes what Mathom does and does not defend against, so
operators can deploy it safely. Mathom is a **local-first, self-hosted**
archive; its security posture assumes a trusted host and a small number of
trusted users.

## Assets

- **Recordings and derived data** — audio files, transcripts, AI summaries, and
  follow-up chat. Often personal or sensitive.
- **The SQLite database** — all metadata plus, when SSO is enabled, user
  accounts and server-side session tokens.
- **The Authentik client secret** — stored in `app_settings` (never returned by
  the API) when SSO is configured.

## Trust boundaries

```
Internet / LAN ──▶ mathom container ──▶ (nginx ──▶ FastAPI backend)
                   only exposed port          │
                                     SQLite + audio volume
                                     Ollama (internal net)
                                     Authentik (only if SSO on)
```

- The **mathom container** is the only one that publishes a port; inside it,
  nginx is the front door and binds to `127.0.0.1` by default.
- **Ollama** is never published; it is reachable only on the internal Compose
  network.
- The **backend** (uvicorn on `127.0.0.1:8000`, in the same container) trusts
  requests that reach it from nginx.

## Actors

| Actor | Assumed capability |
| ----- | ------------------ |
| Local user | Full access to their own Mathoms; SSO scopes data per user. |
| Other LAN devices | Can reach Mathom **only** if `MATHOM_BIND=0.0.0.0`. |
| Malicious upload | Attacker controls the bytes and filename of an upload. |
| Compromised Ollama output | The LLM may return attacker-influenced text (prompt injection via transcript content). |

## What Mathom defends against

- **Unauthenticated network exposure (default).** Loopback-only bind; auth-off
  installs are not reachable off-host unless the operator opts in.
- **Cross-user data access (SSO mode).** Every data query is scoped by
  `user_id`; non-owned rows return `404`, so existence never leaks. RBAC guards
  admin/owner actions, with last-Owner lockout protection.
- **Spoofed uploads.** Extension **and** content are checked: `ffprobe` must
  find a real audio stream before a file reaches whisper. Size is capped
  (`MAX_UPLOAD_MB`); stored filenames are server-generated UUIDs, so the
  original name is never used on disk (no path traversal).
- **Bounded media processing.** FFmpeg/ffprobe run with fixed argument lists (no
  shell), `-nostdin`, a thread cap, and a wall-clock timeout.
- **SQL injection.** All queries use SQLAlchemy parameter binding; FTS input is
  tokenized to a safe prefix query.
- **Resource exhaustion / brute force.** Per-client rate limiting throttles
  uploads, chat, summaries, search, and login attempts.
- **Sensitive-data leakage in errors.** Pipeline failures surface a generic
  message; raw exception text is logged server-side only.
- **Session theft basics.** Session tokens are opaque, server-side, HttpOnly,
  `SameSite=Lax`, and `Secure` by default, with a bounded lifetime (14 days by
  default). OAuth uses a checked `state` token, and the login is bound to the
  ID token's `nonce`.
- **Secret disclosure.** The Authentik client secret is write-only over the API.

## Out of scope (operator's responsibility)

- **A hostile host.** Anyone with root or with access to the data volume can
  read everything. Use disk encryption for sensitive archives.
- **TLS termination.** Mathom speaks HTTP; run it behind a TLS-terminating
  reverse proxy for any non-loopback use, and keep `SESSION_COOKIE_SECURE=true`.
- **Trusting `X-Forwarded-For`.** The rate limiter reads the proxy-supplied
  client IP. Only expose Mathom through the bundled proxy (or one that sets it),
  not directly.
- **Prompt injection consequences.** A transcript can contain text that steers
  the LLM. Treat AI summaries/chat as untrusted narrative, not authority.
- **Authentik's own security.** MFA, password policy, and token signing live in
  Authentik; Mathom delegates authentication entirely to it.
- **Malicious insiders.** A signed-in user is trusted with their own data;
  Mathom is not a hostile-multi-tenant system.

## Residual risks

- The ID token's signature is not cryptographically verified against Authentik's
  JWKS. The token is only used for `nonce` binding — identity comes from the
  userinfo back-channel — and it arrives over server-to-server TLS, so this is
  defense-in-depth rather than a gap. Full JWKS verification is a future step.
- Sessions have an absolute lifetime (14 days by default) but no idle expiry or
  rotation; a stolen cookie is valid until it expires or the user logs out.
- The single worker processes one recording at a time; a very long transcription
  delays others in the queue (throughput, not correctness).

See [SECURITY.md](../SECURITY.md) to report a vulnerability.
