# Security Policy

Mathom is a local-first application intended to run on hardware you control,
on a network you trust. It ships with no authentication layer of its own — do
**not** expose the proxy port directly to the internet. If you need remote
access, put it behind a VPN (e.g. WireGuard, Tailscale) or an authenticating
reverse proxy.

## Design guarantees

- **No cloud, no telemetry.** The stack makes no outbound connections except
  backend → Ollama on the internal Docker network (and model downloads you
  explicitly trigger).
- **Ollama is never published** on a host port; it is reachable only from the
  backend on the internal Compose network.
- **Non-root containers** for backend and proxy.
- **Upload validation**: extension allowlist, size limits, server-generated
  filenames; uploaded files are never executed or shelled into commands.
- **Parameterized SQL** everywhere; FTS queries are tokenized and quoted
  before reaching SQLite.
- Dependencies are scanned in CI (pip-audit, npm audit, Trivy).

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/MacNite/Mathom-House---Your-Local-AI-Memory-House/security/advisories/new)
rather than opening a public issue.

Include: affected version/commit, reproduction steps, and impact. You can
expect an acknowledgement within 7 days. Please allow a reasonable window for
a fix before public disclosure.
