"""Tests for optional local video analysis.

No network, no ffmpeg, no models: ffprobe/ffmpeg and the Ollama vision calls
are mocked. These cover the pure sampling logic, stream probing, and the
router/health guards that gate the feature.
"""

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import vision


def test_timestamps_without_duration(client: TestClient) -> None:
    assert vision._timestamps(None) == [0.0]
    assert vision._timestamps(0) == [0.0]


def test_timestamps_regular_interval(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "vision_sample_interval_seconds", 30)
    monkeypatch.setattr(settings, "vision_max_frames", 24)
    stamps = vision._timestamps(60)
    assert stamps[0] == 0.0
    assert stamps[-1] == pytest.approx(59.9)
    assert 30.0 in stamps


def test_timestamps_downsamples_to_max_frames(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "vision_sample_interval_seconds", 10)
    monkeypatch.setattr(settings, "vision_max_frames", 3)
    stamps = vision._timestamps(100)
    assert len(stamps) == 3
    assert stamps[0] == 0.0
    assert stamps[-1] == pytest.approx(99.9)
    assert stamps == sorted(stamps)


@pytest.mark.parametrize(
    ("streams", "expected"),
    [
        ([{"codec_type": "audio"}, {"codec_type": "video"}], (True, True)),
        ([{"codec_type": "audio"}], (True, False)),
        ([{"codec_type": "video"}], (False, True)),
    ],
)
def test_media_streams_parses_ffprobe(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    streams: list[dict[str, str]],
    expected: tuple[bool, bool],
) -> None:
    payload = {
        "streams": streams,
        "format": {"duration": "12.5"},
    }

    class FakeResult:
        stdout = json.dumps(payload)

    called: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> FakeResult:
        called["args"] = args
        called["kwargs"] = kwargs
        return FakeResult()

    monkeypatch.setattr(vision.subprocess, "run", fake_run)
    has_audio, has_video, duration = vision.media_streams(Path("clip.mp4"))
    args = called["args"]
    assert isinstance(args, list)
    assert args[0] == "ffprobe"
    assert "-nostdin" not in args
    kwargs = called["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert (has_audio, has_video) == expected
    assert duration == pytest.approx(12.5)


def test_media_streams_raises_on_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> object:
        raise vision.subprocess.SubprocessError("ffprobe failed")

    monkeypatch.setattr(vision.subprocess, "run", boom)
    with pytest.raises(vision.VisionError):
        vision.media_streams(Path("clip.mp4"))


def test_media_streams_raises_on_invalid_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeResult:
        stdout = "not json"

    monkeypatch.setattr(vision.subprocess, "run", lambda *a, **k: FakeResult())
    with pytest.raises(vision.VisionError):
        vision.media_streams(Path("clip.mp4"))


def test_visual_analysis_disabled_by_default(client: TestClient, wait_for_status) -> None:  # type: ignore[no-untyped-def]
    created = client.post("/api/mathoms/text", json={"text": "content"}).json()
    wait_for_status(client, created["id"])
    response = client.post(
        f"/api/mathoms/{created['id']}/visual-analysis",
        json={"regenerate_summary": False},
    )
    assert response.status_code == 409


def test_visual_analysis_requires_video(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, wait_for_status
) -> None:  # type: ignore[no-untyped-def]
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "vision_enabled", True)
    created = client.post("/api/mathoms/text", json={"text": "content"}).json()
    wait_for_status(client, created["id"])
    response = client.post(
        f"/api/mathoms/{created['id']}/visual-analysis",
        json={"regenerate_summary": False},
    )
    assert response.status_code == 422


def test_upload_rejects_visuals_when_disabled(client: TestClient) -> None:
    # analyze_visuals on an ordinary audio upload while vision is off: the
    # server must refuse rather than silently ignore the request.
    response = client.post(
        "/api/mathoms",
        files={"file": ("clip.mp3", __import__("io").BytesIO(b"fake"), "audio/mpeg")},
        data={"analyze_visuals": "true"},
    )
    # ffprobe classifies the fake bytes as having no video stream first.
    assert response.status_code == 422


def test_upload_accepts_valid_mp4_streams(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vision, "media_streams", lambda path: (True, True, 12.5))

    response = client.post(
        "/api/mathoms",
        files={"file": ("whatsapp.mp4", __import__("io").BytesIO(b"fake"), "video/mp4")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_type"] == "video"
    assert body["has_audio_stream"] is True
    assert body["has_video_stream"] is True


def test_health_reports_vision_state(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["vision_enabled"] is False
    assert body["vision_model_installed"] is None


def test_health_probes_vision_when_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "vision_enabled", True)
    monkeypatch.setattr(vision, "_show", lambda: None)
    body = client.get("/api/health").json()
    assert body["vision_enabled"] is True
    assert body["vision_model_installed"] is True
    assert body["vision_model_has_vision"] is True
