"""Tests for optional, local-only speaker diarization."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import diarization

SEGMENTS = [
    {"start": 0.0, "end": 2.0, "text": "First"},
    {"start": 2.0, "end": 4.0, "text": "Second"},
]


def test_label_segments_is_unchanged_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        diarization, "get_settings", lambda: SimpleNamespace(diarization_enabled=False)
    )
    assert diarization.label_segments(SEGMENTS) == SEGMENTS


def test_label_segments_merges_speaker_with_greatest_overlap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model_path = tmp_path / "diarization"
    model_path.mkdir()
    audio_path = tmp_path / "recording.wav"
    audio_path.touch()
    settings = SimpleNamespace(diarization_enabled=True, diarization_model_path=model_path)
    monkeypatch.setattr(diarization, "get_settings", lambda: settings)

    class Turn:
        def __init__(self, start: float, end: float) -> None:
            self.start = start
            self.end = end

    class Result:
        def itertracks(self, *, yield_label: bool):
            assert yield_label
            return iter(
                [
                    (Turn(0.0, 1.5), None, "SPEAKER_00"),
                    (Turn(1.5, 4.0), None, "SPEAKER_01"),
                ]
            )

    monkeypatch.setattr(diarization, "_load_pipeline", lambda path: lambda audio: Result())
    labeled = diarization.label_segments([dict(segment) for segment in SEGMENTS], audio_path)
    assert [segment.get("speaker") for segment in labeled] == ["SPEAKER_00", "SPEAKER_01"]


def test_label_segments_falls_back_when_provider_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model_path = tmp_path / "diarization"
    model_path.mkdir()
    monkeypatch.setattr(
        diarization,
        "get_settings",
        lambda: SimpleNamespace(diarization_enabled=True, diarization_model_path=model_path),
    )
    monkeypatch.setattr(
        diarization,
        "_load_pipeline",
        lambda path: (_ for _ in ()).throw(ImportError("pyannote is absent")),
    )
    segments = [dict(segment) for segment in SEGMENTS]
    assert diarization.label_segments(segments, tmp_path / "recording.wav") == segments
