"""A small, dependency-free per-client rate limiter.

Mathom is a single-process app behind its own nginx proxy, so an in-memory
fixed-window counter is enough to protect the box from a runaway client or a
login brute-force. There is deliberately no external store (Redis) — that would
break the local-first, one-stack philosophy.

Two budgets are enforced per client per minute:

* a generous one for cheap reads, and
* a tight one for expensive work — uploads, chat, summaries, search, and any
  auth/login attempt (the brute-force surface).

The client key prefers ``X-Real-IP`` (the bundled nginx proxy sets it to the
real socket address, which a client cannot forge) and falls back to the
right-most ``X-Forwarded-For`` entry — the hop nginx appended — never the
client-supplied left-most value, which would let a caller mint a fresh bucket
per request and sail past the limiter.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

_WINDOW_SECONDS = 60

# Expensive endpoints keyed by (method, path-prefix). Any mutating request plus
# the two costly GETs (search, login redirect) fall in the "heavy" bucket.
_HEAVY_PREFIXES = ("/api/auth/login", "/api/auth/callback", "/api/search")


def _client_key(request: Request) -> str:
    # X-Real-IP is set by our own nginx to the socket peer, so it cannot be
    # spoofed by the client. Prefer it.
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    # Otherwise use the right-most X-Forwarded-For hop — the one the nearest
    # trusted proxy appended. The left-most entries are client-supplied and must
    # never key the limiter, or a caller could rotate them to evade throttling.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def _is_heavy(request: Request) -> bool:
    if request.method != "GET":
        return True
    return any(request.url.path.startswith(p) for p in _HEAVY_PREFIXES)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-client limiter. State is a small in-memory dict."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        # (client_key, bucket) -> (window_start_epoch, count)
        self._hits: dict[tuple[str, str], tuple[int, int]] = defaultdict(lambda: (0, 0))

    def _check(self, key: str, bucket: str, limit: int) -> int | None:
        """Register a hit. Returns seconds-to-wait if over the limit, else None."""
        now = int(time.time())
        window = now - (now % _WINDOW_SECONDS)
        start, count = self._hits[(key, bucket)]
        if start != window:
            self._hits[(key, bucket)] = (window, 1)
            return None
        if count >= limit:
            return window + _WINDOW_SECONDS - now
        self._hits[(key, bucket)] = (window, count + 1)
        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        # The container healthcheck must never be throttled.
        if not settings.rate_limit_enabled or request.url.path == "/api/health":
            return await call_next(request)

        heavy = _is_heavy(request)
        limit = settings.rate_limit_heavy_per_minute if heavy else settings.rate_limit_per_minute
        retry_after = self._check(_client_key(request), "heavy" if heavy else "read", limit)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
