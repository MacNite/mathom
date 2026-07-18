"""Speech-to-text via faster-whisper, with FFmpeg for probing and normalizing.

faster-whisper is an optional dependency (the `ml` extra) so the test suite and
CI never need model weights. Import happens lazily on first use.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings

_model: Any = None


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
            timeout=60,
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
            "-y",
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
        timeout=600,
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


def transcribe(audio_path: Path) -> tuple[str, str | None]:
    """Transcribe an audio file. Returns (transcript_text, detected_language)."""
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        _to_wav(audio_path, wav_path)
        model = _get_model()
        segments, info = model.transcribe(str(wav_path), vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    language = getattr(info, "language", None)
    return text, language
