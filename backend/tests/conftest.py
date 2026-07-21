"""Shared fixtures. Whisper and Ollama are always mocked — tests never need
models, network, or FFmpeg."""

import io
import os
import tempfile
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]


def _wait_for_status(
    client: TestClient,
    mathom_id: int,
    *,
    among: tuple[str, ...] = ("ready", "error"),
    timeout: float = 10.0,
) -> dict:
    """Poll a Mathom until the durable worker moves it into a terminal state."""
    deadline = time.monotonic() + timeout
    detail: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/mathoms/{mathom_id}")
        assert response.status_code == 200, response.text
        detail = response.json()
        if detail["status"] in among:
            return detail
        time.sleep(0.05)
    raise AssertionError(f"Mathom {mathom_id} stuck in status {detail.get('status')!r}")


@pytest.fixture()
def wait_for_status():  # type: ignore[no-untyped-def]
    """Expose the poll helper to tests as a fixture.

    Bare ``pytest`` (as CI runs it) does not put the repo on ``sys.path``, so
    ``from tests.conftest import ...`` is not importable — fixtures are the
    portable way to share helpers.
    """
    return _wait_for_status


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MATHOM_DATA_DIR"] = tmp
        os.environ["MATHOM_TEMPLATES_DIR"] = str(REPO_ROOT / "prompt-templates")
        # The limiter is exercised in test_ratelimit.py; keep it out of the way
        # of suites that fire many requests in one window.
        os.environ["MATHOM_RATE_LIMIT_ENABLED"] = "false"

        # Reset module-level singletons so each test gets a fresh database.
        import app.config as config
        import app.db as db

        config.get_settings.cache_clear()
        db._engine = None
        db._session_factory = None

        from app.services import ollama, transcription

        monkeypatch.setattr(ollama, "chat", lambda messages, language=None: "Mocked AI reply.")
        monkeypatch.setattr(ollama, "is_reachable", lambda: False)
        monkeypatch.setattr(
            transcription,
            "transcribe",
            lambda path: (
                "This is a mocked transcript.",
                "en",
                [{"start": 0.0, "end": 1.0, "text": "This is a mocked transcript."}],
            ),
        )
        monkeypatch.setattr(transcription, "probe_duration_seconds", lambda path: 12.5)
        monkeypatch.setattr(transcription, "validate_audio", lambda path: None)

        from app.main import app

        with TestClient(app) as test_client:
            yield test_client

        db._engine = None
        db._session_factory = None
        config.get_settings.cache_clear()


@dataclass
class AuthHarness:
    """Drives the Authentik login flow against the running app with OIDC mocked."""

    app: object
    claims: dict = field(default_factory=dict)

    def client(self) -> TestClient:
        """A fresh client with its own cookie jar (i.e. a distinct browser)."""
        return TestClient(self.app)

    def login(self, client: TestClient, claims: dict) -> None:
        """Complete a full login for ``claims``; leaves the session cookie set."""
        self.claims.clear()
        self.claims.update(claims)
        start = client.get("/api/auth/login", follow_redirects=False)
        assert start.status_code == 302, start.text
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        done = client.get(
            f"/api/auth/callback?code=fake-code&state={state}", follow_redirects=False
        )
        assert done.status_code == 302, done.text
        assert "auth_error" not in done.headers["location"], done.headers["location"]


_AUTH_ENV = {
    "MATHOM_AUTH_ENABLED": "true",
    "MATHOM_AUTHENTIK_ISSUER": "https://auth.example.com/application/o/mathom",
    "MATHOM_AUTHENTIK_CLIENT_ID": "mathom",
    "MATHOM_AUTHENTIK_CLIENT_SECRET": "top-secret",
    "MATHOM_SESSION_COOKIE_SECURE": "false",  # TestClient speaks http
}


@pytest.fixture()
def auth_harness(monkeypatch: pytest.MonkeyPatch) -> Generator[AuthHarness, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MATHOM_DATA_DIR"] = tmp
        os.environ["MATHOM_TEMPLATES_DIR"] = str(REPO_ROOT / "prompt-templates")
        os.environ["MATHOM_RATE_LIMIT_ENABLED"] = "false"
        os.environ.update(_AUTH_ENV)

        import app.config as config
        import app.db as db

        config.get_settings.cache_clear()
        db._engine = None
        db._session_factory = None

        from app.services import oidc, ollama, transcription

        monkeypatch.setattr(ollama, "chat", lambda messages, language=None: "Mocked AI reply.")
        monkeypatch.setattr(ollama, "is_reachable", lambda: False)
        monkeypatch.setattr(
            transcription,
            "transcribe",
            lambda path: (
                "This is a mocked transcript.",
                "en",
                [{"start": 0.0, "end": 1.0, "text": "This is a mocked transcript."}],
            ),
        )
        monkeypatch.setattr(transcription, "probe_duration_seconds", lambda path: 12.5)
        monkeypatch.setattr(transcription, "validate_audio", lambda path: None)

        harness = AuthHarness(app=None)

        monkeypatch.setattr(
            oidc,
            "discover",
            lambda config: {
                "authorization_endpoint": "https://auth.example.com/authorize",
                "token_endpoint": "https://auth.example.com/token",
                "userinfo_endpoint": "https://auth.example.com/userinfo",
            },
        )
        monkeypatch.setattr(
            oidc, "exchange_code", lambda config, **kw: {"access_token": "fake-token"}
        )
        monkeypatch.setattr(oidc, "fetch_userinfo", lambda config, **kw: dict(harness.claims))

        from app.main import app as fastapi_app

        harness.app = fastapi_app
        # Trigger startup (init_db + seed) once via a throwaway client.
        with TestClient(fastapi_app):
            pass
        yield harness

        db._engine = None
        db._session_factory = None
        config.get_settings.cache_clear()
        for key in _AUTH_ENV:
            os.environ.pop(key, None)


@pytest.fixture()
def uploaded_mathom(client: TestClient) -> dict:
    """Upload a fake recording; background pipeline runs with mocked services."""
    response = client.post(
        "/api/mathoms",
        files={"file": ("greeting.mp3", io.BytesIO(b"fake-audio-bytes"), "audio/mpeg")},
        data={"title": "A test recording"},
    )
    assert response.status_code == 201, response.text
    mathom_id = response.json()["id"]
    # Processing now runs in the durable worker thread, so wait for it to land.
    return _wait_for_status(client, mathom_id)
