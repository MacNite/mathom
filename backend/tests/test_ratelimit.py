"""The in-process rate limiter returns 429 once a client's budget is spent."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def limited_client() -> Generator[TestClient, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MATHOM_DATA_DIR"] = tmp
        os.environ["MATHOM_TEMPLATES_DIR"] = str(REPO_ROOT / "prompt-templates")
        os.environ["MATHOM_RATE_LIMIT_ENABLED"] = "true"
        os.environ["MATHOM_RATE_LIMIT_HEAVY_PER_MINUTE"] = "3"
        os.environ["MATHOM_RATE_LIMIT_PER_MINUTE"] = "1000"

        import app.config as config
        import app.db as db

        config.get_settings.cache_clear()
        db._engine = None
        db._session_factory = None

        from app.main import app

        with TestClient(app) as client:
            yield client

        db._engine = None
        db._session_factory = None
        config.get_settings.cache_clear()
        for key in (
            "MATHOM_RATE_LIMIT_ENABLED",
            "MATHOM_RATE_LIMIT_HEAVY_PER_MINUTE",
            "MATHOM_RATE_LIMIT_PER_MINUTE",
        ):
            os.environ.pop(key, None)


def test_heavy_endpoint_is_throttled(limited_client: TestClient) -> None:
    # Search is a "heavy" GET; budget is 3/min in this fixture.
    for _ in range(3):
        assert limited_client.get("/api/search", params={"q": "x"}).status_code == 200
    blocked = limited_client.get("/api/search", params={"q": "x"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_spoofed_forwarded_for_cannot_evade_limit(limited_client: TestClient) -> None:
    # A client-supplied left-most X-Forwarded-For must not mint a fresh bucket:
    # the limiter keys on X-Real-IP (set by the trusted proxy) instead.
    headers = {"X-Real-IP": "203.0.113.7"}
    for _ in range(3):
        assert (
            limited_client.get(
                "/api/search",
                params={"q": "x"},
                headers={**headers, "X-Forwarded-For": f"{_}.{_}.{_}.{_}"},
            ).status_code
            == 200
        )
    blocked = limited_client.get(
        "/api/search",
        params={"q": "x"},
        headers={**headers, "X-Forwarded-For": "9.9.9.9"},
    )
    assert blocked.status_code == 429


def test_health_is_never_throttled(limited_client: TestClient) -> None:
    # The container healthcheck must always answer.
    for _ in range(10):
        assert limited_client.get("/api/health").status_code == 200
