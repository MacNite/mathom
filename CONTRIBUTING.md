# Contributing to Mathom

Thanks for helping build the mathom! This guide covers the practical
bits; [CLAUDE.md](CLAUDE.md) is the authoritative reference for architecture
and standards.

## Getting set up

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

# Frontend
cd frontend
npm install
npm test
```

`./scripts/dev.sh` runs both apps in dev mode without Docker.

## Workflow

1. Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`
2. Make your change, with tests.
3. Run the full check locally: `make lint && make test`
4. Add a bullet to the `[Unreleased]` section of [CHANGELOG.md](CHANGELOG.md)
   when the change is user-visible.
5. Open a Pull Request. CI must be green; `main` is protected.

CI runs `backend-ci` (ruff, mypy, pytest), `frontend-ci` (eslint, tsc, vitest,
build), `compose-validation` (both stacks), `docker-build`, and `security`
(pip-audit, npm audit, Trivy, SBOM). If you touch `compose.yaml`, `Dockerfile`,
or `.env.example`, run `make validate` before pushing.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(backend): add FTS5 search across transcripts
fix(frontend): keep chat scroll pinned to bottom
```

## Code standards (short version)

- **Python**: typed, `ruff` + `mypy` clean, business logic in
  `app/services/`, external calls mocked in tests.
- **TypeScript**: strict mode, all API calls through `src/lib/api.ts`,
  Tailwind theme colors only.
- **Tests must run offline** — never require whisper models, Ollama, or the
  network.
- User-facing copy follows the brand voice: warm, calm, minimal.

## What makes a good PR

- One concern per PR, small enough to review in one sitting.
- Tests that fail without your change.
- Docs updated when behavior changes (`README.md`, `docs/`, `.env.example`).
- New configuration documented in `.env.example` *and* the README table, with a
  safe default. Anything that widens Mathom's exposure defaults to off.

## Reporting a security issue

Please **do not** open a public issue or PR for a vulnerability. Report it
privately through [GitHub Security Advisories](https://github.com/MacNite/mathom/security/advisories/new);
[SECURITY.md](SECURITY.md) covers what to include, what to expect, and which
known limits are deliberate rather than bugs. If a change of yours has security
relevance, say so in the PR description and check it against the
[threat model](docs/threat-model.md).
