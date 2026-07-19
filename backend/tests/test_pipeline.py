"""Reliability + safety of the processing pipeline: restart recovery, safe
user-facing errors, and ffprobe-based upload validation."""

import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.models import Mathom
from app.services import pipeline, transcription


def _make_mathom(status: str) -> int:
    with get_session_factory()() as session:
        mathom = Mathom(title="stuck", audio_path="/data/audio/x.mp3", status=status)
        session.add(mathom)
        session.commit()
        session.refresh(mathom)
        return mathom.id


def test_recover_interrupted_jobs_resets_in_flight(client: TestClient) -> None:
    ids = {status: _make_mathom(status) for status in ("pending", "transcribing", "summarizing")}
    ready_id = _make_mathom("ready")

    reset = pipeline.recover_interrupted_jobs()
    assert reset == 3

    with get_session_factory()() as session:
        for status_id in ids.values():
            row = session.get(Mathom, status_id)
            assert row is not None
            assert row.status == "error"
            assert row.error_message == pipeline.INTERRUPTED_MESSAGE
        # A finished job is untouched.
        assert session.get(Mathom, ready_id).status == "ready"


def test_recover_interrupted_jobs_noop_when_clean(client: TestClient) -> None:
    _make_mathom("ready")
    assert pipeline.recover_interrupted_jobs() == 0


@pytest.mark.parametrize(
    "exc",
    [
        transcription.AudioValidationError("no audio"),
        subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1),
        httpx.ConnectError("connection refused"),
        RuntimeError("/data/audio/secret-path.mp3 blew up"),
    ],
)
def test_safe_error_never_leaks_internals(exc: Exception) -> None:
    message = pipeline._safe_error(exc)
    # The raw exception text (which may contain paths or upstream bodies) is
    # never echoed back to the user.
    assert str(exc) not in message
    assert message  # always something friendly


def test_validate_audio_rejects_non_audio(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(transcription, "_ffprobe_streams", lambda path: [])
    with pytest.raises(transcription.AudioValidationError):
        transcription.validate_audio(tmp_path / "not-audio.mp3")


def test_validate_audio_accepts_audio_stream(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(transcription, "_ffprobe_streams", lambda path: [{"codec_type": "audio"}])
    # Should not raise.
    transcription.validate_audio(tmp_path / "real.mp3")


def test_pipeline_marks_error_on_invalid_audio(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mathom_id = _make_mathom("pending")
    monkeypatch.setattr(
        transcription,
        "validate_audio",
        lambda path: (_ for _ in ()).throw(transcription.AudioValidationError("bad")),
    )
    pipeline.process_mathom(mathom_id)
    with get_session_factory()() as session:
        row = session.get(Mathom, mathom_id)
        assert row.status == "error"
        assert "valid recording" in row.error_message
