"""Optional speaker labels; CPU installations default to a no-op."""

from app.config import get_settings


def label_segments(segments: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return segments with optional speaker labels when a provider is installed.

    The default intentionally avoids loading a model, keeping diarization opt-in.
    """
    if not get_settings().diarization_enabled:
        return segments
    # A provider can be added here without changing pipeline or storage contracts.
    return segments
