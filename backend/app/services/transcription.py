"""Speech-to-text via faster-whisper, with FFmpeg for probing and normalizing.

faster-whisper is an optional dependency (the `ml` extra) so the test suite and
CI never need model weights. Import happens lazily on first use.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings

_model: Any = None

# FFmpeg/ffprobe run on untrusted uploads, so every invocation is bounded:
# fixed argument lists (no shell), a hard wall-clock timeout, `-nostdin` so a
# malformed file can never make the process wait for input, and a thread cap so
# one recording cannot saturate every core.
_PROBE_TIMEOUT = 60
_FFMPEG_THREADS = "1"


class AudioValidationError(ValueError):
    """Raised when an uploaded file is not decodable audio."""


def _ffprobe_streams(audio_path: Path) -> list[dict[str, Any]]:
    """Return the stream list ffprobe reports, or [] if the file is unreadable."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type:format=duration",
                "-of",
                "json",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
            check=True,
        )
        data = json.loads(result.stdout or "{}")
    except (subprocess.SubprocessError, ValueError, OSError):
        return []
    return list(data.get("streams", []))


def validate_audio(audio_path: Path) -> None:
    """Confirm the file is real, decodable audio before it reaches whisper.

    Extension checks are trivially spoofed, so we ask ffprobe what the bytes
    actually are and require at least one audio stream. Raises
    ``AudioValidationError`` otherwise.
    """
    streams = _ffprobe_streams(audio_path)
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise AudioValidationError("no decodable audio stream found")


def probe_duration_seconds(audio_path: Path) -> float | None:
    """Return audio duration using ffprobe, or None if it cannot be determined."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
            stdin=subprocess.DEVNULL,
            check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _to_wav(audio_path: Path, target: Path) -> None:
    """Normalize any input container to 16 kHz mono WAV for whisper."""
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-threads",
            _FFMPEG_THREADS,
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            str(target),
        ],
        capture_output=True,
        timeout=get_settings().ffmpeg_timeout_seconds,
        check=True,
    )


def _get_model() -> Any:
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # heavy import, deferred

        settings = get_settings()
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


def transcribe(audio_path: Path) -> tuple[str, str | None, list[dict[str, object]]]:
    """Transcribe an audio file and preserve timestamped segment data."""
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        _to_wav(audio_path, wav_path)
        model = _get_model()
        segments, info = model.transcribe(
            str(wav_path),
            vad_filter=True,
            initial_prompt=get_settings().whisper_initial_prompt or None,
        )
        segment_data = [
            {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip()}
            for segment in segments
            if segment.text.strip()
        ]
        text = " ".join(str(segment["text"]) for segment in segment_data).strip()
    language = getattr(info, "language", None)
    return text, language, segment_data
