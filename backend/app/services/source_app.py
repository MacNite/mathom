"""Best-effort detection of the app a recording came from.

The platform never tells us which app shared a file, but many messengers name
their exported media recognisably (a WhatsApp voice note is
``PTT-20260722-WA0004.opus``). Detecting from the filename lets Mathom label and
filter recordings by origin. Unknown names return ``None`` and carry no origin.

The rules here mirror ``frontend/src/lib/sourceApp.ts`` so the badge shown at
upload time and the value stored on the server stay in agreement.
"""

import re
from datetime import UTC, date, datetime, time

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # WhatsApp: PTT-/AUD-/VID-/IMG-<date>-WA####.<ext>, or a "WhatsApp …" name.
    ("WhatsApp", re.compile(r"-WA\d+\.|^whatsapp[ _-]", re.IGNORECASE)),
    # Telegram: voice_/audio_<date>_… exports, or a "Telegram …" name.
    ("Telegram", re.compile(r"^(voice|audio)_\d{4}-\d{2}-\d{2}|telegram", re.IGNORECASE)),
    # Signal: signal-<date>-… exports.
    ("Signal", re.compile(r"^signal-\d{4}-\d{2}-\d{2}|^signal[ _-]", re.IGNORECASE)),
)


def detect_source_app(filename: str | None) -> str | None:
    """Return the app a file most likely came from, or ``None`` when the
    filename carries no recognisable signal. Brand names are not translated."""
    if not filename:
        return None
    name = filename.strip()
    for label, pattern in _RULES:
        if pattern.search(name):
            return label
    return None


# A date, optionally followed by a time, as recorders and messengers embed it:
# PTT-20260722-WA0004, audio_2026-07-22_14-03-11, signal-2026-07-22-140311,
# REC_20260722_140311, "Recording 2026-07-22 14.03.11".
_DATE_IN_NAME = re.compile(
    r"(?<!\d)(?P<y>20\d{2})-?(?P<m>[01]\d)-?(?P<d>[0-3]\d)"
    r"(?:[ _T-](?P<H>[0-2]\d)[-:.]?(?P<M>[0-5]\d)[-:.]?(?P<S>[0-5]\d))?(?!\d)"
)


def detect_recorded_at(filename: str | None, mtime: float | None = None) -> datetime | None:
    """Best guess at when a recording was made, from its name and file time.

    A full date+time in the name wins (read as the server's local time). A
    date-only name (WhatsApp) uses the file's modification time when it falls
    on that day — sync tools like Syncthing preserve it — else local noon of
    that date. Without a date in the name, the modification time is used.
    """
    file_time = datetime.fromtimestamp(mtime, UTC) if mtime else None
    match = _DATE_IN_NAME.search(filename or "")
    if not match:
        return file_time
    try:
        day = date(int(match["y"]), int(match["m"]), int(match["d"]))
        if match["H"]:
            local = datetime.combine(day, time(int(match["H"]), int(match["M"]), int(match["S"])))
            return local.astimezone(UTC)
    except ValueError:
        return file_time
    if file_time is not None and file_time.astimezone().date() == day:
        return file_time
    return datetime.combine(day, time(12, 0)).astimezone(UTC)
