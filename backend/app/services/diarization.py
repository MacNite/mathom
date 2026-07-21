"""Optional local speaker diarization for timestamped transcript segments."""

import importlib
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from app.config import get_settings

logger = logging.getLogger("mathom.diarization")


def _overlap(start: float, end: float, turn_start: float, turn_end: float) -> float:
    return max(0.0, min(end, turn_end) - max(start, turn_start))


def _load_pipeline(model_path: Path) -> Any:
    """Lazily load pyannote only for explicitly enabled local diarization."""
    module = importlib.import_module("pyannote.audio")
    return module.Pipeline.from_pretrained(str(model_path))


def _speaker_turns(result: Any) -> Iterable[tuple[float, float, str]]:
    for turn, _, speaker in result.itertracks(yield_label=True):
        yield float(turn.start), float(turn.end), str(speaker)


def label_segments(
    segments: list[dict[str, object]], audio_path: Path | None = None
) -> list[dict[str, object]]:
    """Return segments with optional speaker labels when a provider is installed.

    The default intentionally avoids loading a model, keeping diarization opt-in.
    """
    if not get_settings().diarization_enabled:
        return segments
    settings = get_settings()
    if audio_path is None or settings.diarization_model_path is None:
        logger.warning("Diarization is enabled but no local model path or audio path is available")
        return segments
    if not settings.diarization_model_path.exists():
        logger.warning("Diarization model path does not exist: %s", settings.diarization_model_path)
        return segments
    try:
        pipeline = _load_pipeline(settings.diarization_model_path)
        turns = list(_speaker_turns(pipeline(str(audio_path))))
    except Exception as exc:  # noqa: BLE001 - optional provider must never stop transcription
        logger.warning("Local diarization is unavailable; leaving segments unlabeled: %s", exc)
        return segments

    for segment in segments:
        start = float(cast(Any, segment["start"]))
        end = float(cast(Any, segment["end"]))
        labels: dict[str, float] = {}
        for turn_start, turn_end, speaker in turns:
            labels[speaker] = labels.get(speaker, 0.0) + _overlap(start, end, turn_start, turn_end)
        if labels:
            segment["speaker"] = max(labels, key=labels.__getitem__)
    return segments
