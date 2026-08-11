# Security Policy

Mathom is a local-first application intended to run on hardware you control.
It ships closed: with authentication disabled — the default — the web UI binds
to `127.0.0.1` and is reachable only from the host. Widening that
(`MATHOM_BIND=0.0.0.0`) puts an unauthenticated archive on your network, so do
it only behind a VPN (WireGuard, Tailscale) or an authenticating reverse proxy,
or after enabling single sign-on. Never port-forward Mathom to the internet
as-is.

See the [exposure warning](docs/deployment.md#exposure-warning) before Mathom is
reachable by anyone but you, and the [threat model](docs/threat-model.md) for
what it does and does not defend against.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅ Yes    |
| < 0.1   | ❌ No (pre-release) |

Only the latest release receives security fixes. Mathom is pre-1.0: fixes land
in a new patch release rather than being backported.

## Design guarantees

**Network posture**

- **No cloud, no telemetry.** The stack makes no outbound connections except
  backend → Ollama on the internal Docker network, backend → Authentik when you
  enable SSO, and model downloads you explicitly trigger.
- **Ollama is never published** on a host port; it is reachable only from the
  backend on the internal Compose network.
- **Loopback by default.** Only the mathom container publishes a port, and it
  binds to `127.0.0.1` unless you opt out.
- **Content-Security-Policy and HSTS** are set at the proxy; the self-contained
  frontend is locked to `'self'`.

**Input handling**

- **Upload validation** by extension *and* content — `ffprobe` must find a real
  media stream before a file reaches whisper. Size is capped (`MAX_UPLOAD_MB`,
  `MATHOM_MAX_DOCUMENT_MB`), and stored filenames are server-generated UUIDs, so
  a caller-supplied name never touches the filesystem.
- **Bounded media processing** — FFmpeg and ffprobe run with fixed argument
  lists (never a shell), `-nostdin`, a thread cap, and a wall-clock timeout.
- **Parameterized SQL** everywhere via SQLAlchemy; FTS input is tokenized and
  quoted before reaching SQLite.
- **Per-client rate limiting** on uploads, chat, summaries, search, and the
  login surface. The client key comes from the proxy-set address, so a
  caller-supplied `X-Forwarded-For` cannot mint a fresh bucket.

**Accounts and sessions** (when authentication is enabled)

- Session tokens are opaque and server-side, in `HttpOnly`, `SameSite=Lax`,
  `Secure` cookies with a bounded lifetime (14 days by default,
  `SESSION_TTL_HOURS`).
- OAuth/OIDC logins carry a checked `state` token and are bound to the ID
  token's `nonce`, so a replayed or injected token is rejected.
- Data is scoped per user; rows you do not own return `404`, so their existence
  never leaks.
- The Authentik client secret is write-only over the API.

**Operational**

- **Non-root containers** — the mathom image (nginx + backend) and Ollama both
  run as non-root users.
- **Safe user-facing errors.** Pipeline failures surface a generic message;
  raw exception text is logged server-side only.
- Dependencies are scanned in CI (pip-audit, npm audit, Trivy) and a CycloneDX
  SBOM is archived with every run.

## Reporting a vulnerability

Please report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/MacNite/mathom/security/advisories/new)
rather than opening a public issue.

Include the affected version or commit, reproduction steps, and the impact you
believe it has. You can expect an acknowledgement within 7 days. Please allow a
reasonable window for a fix before public disclosure — Mathom is maintained by
volunteers, and a private report gives self-hosters time to upgrade.

### Known limits, not vulnerabilities

These are documented, deliberate positions rather than bugs. Reporting them is
welcome as a discussion, but they will not be treated as advisories:

- **A hostile host.** Anyone with root, or with access to the data volume, can
  read every recording. Use disk encryption for sensitive archives.
- **Deliberate exposure.** Setting `MATHOM_BIND=0.0.0.0` with authentication off
  makes an unauthenticated archive reachable — that is the documented meaning of
  the setting, and both the README and the deployment guide warn against it.
- **No TLS of its own.** Mathom speaks HTTP and expects a TLS-terminating
  reverse proxy for any non-loopback use.
- **Prompt injection through transcripts.** A recording can contain text that
  steers the model. Treat AI summaries and chat as untrusted narrative, not
  authority.
- **Queue saturation by a signed-in user.** A trusted user can fill the
  processing queue; `MAX_QUEUED_JOBS` bounds it, but Mathom is not a
  hostile-multi-tenant system.

The [threat model](docs/threat-model.md) also lists the **residual risks** we
know about and intend to close — including ID token signatures not yet being
verified against Authentik's JWKS, and sessions having no idle expiry or
rotation. Findings that deepen or disprove those are especially useful.
