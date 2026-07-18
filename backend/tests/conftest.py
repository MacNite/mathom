"""Shared fixtures. Whisper and Ollama are always mocked — tests never need
models, network, or FFmpeg."""

import io
import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MATHOM_DATA_DIR"] = tmp
        os.environ["MATHOM_TEMPLATES_DIR"] = str(REPO_ROOT / "prompt-templates")

        # Reset module-level singletons so each test gets a fresh database.
        import app.config as config
        import app.db as db

        config.get_settings.cache_clear()
        db._engine = None
        db._session_factory = None

        from app.services import ollama, transcription

        monkeypatch.setattr(ollama, "chat", lambda messages: "Mocked AI reply.")
        monkeypatch.setattr(ollama, "is_reachable", lambda: False)
        monkeypatch.setattr(
            transcription, "transcribe", lambda path: ("This is a mocked transcript.", "en")
        )
        monkeypatch.setattr(transcription, "probe_duration_seconds", lambda path: 12.5)

        from app.main import app

        with TestClient(app) as test_client:
            yield test_client

        db._engine = None
        db._session_factory = None
        config.get_settings.cache_clear()


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
    detail = client.get(f"/api/mathoms/{mathom_id}")
    assert detail.status_code == 200
    return detail.json()
