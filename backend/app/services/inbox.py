"""The watched folder: import new recordings that appear in ``MATHOM_INBOX_DIR``.

Typical setup: Syncthing on an Android phone sends WhatsApp's "Voice Notes"
folder one way to the NAS, and that directory is mounted (read-only is fine)
into the container. Every ``inbox_poll_seconds`` the watcher walks the tree:

- hidden files/folders and temp files are ignored; only the upload extension
  allowlist (audio + video) is considered;
- a file must look the same (size and mtime) on two consecutive scans before
  it is touched, so half-copied files are never imported;
- files are **never modified**. The ``ingest_ledger`` table remembers each
  handled path (and its SHA-256), so a file imports once — even if its Mathom
  is later deleted — and identical content under a second name is skipped;
- a full processing queue simply defers the rest to the next scan.

Imported recordings get an AI-written title, ``recorded_at`` guessed from the
filename/mtime, the origin tag (WhatsApp, Telegram, …), and are owned by
``inbox_owner_email`` when auth is enabled.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session_factory
from app.models import IngestLedgerEntry, User
from app.services import ingest
from app.services.source_app import detect_recorded_at
from app.services.worker import worker

logger = logging.getLogger("mathom.inbox")

_TEMP_SUFFIXES = (".tmp", ".part", ".crdownload", ".partial", "~")


class InboxConfigError(Exception):
    """The inbox is configured but cannot run (missing folder or owner)."""


@dataclass
class ScanResult:
    imported: int = 0
    skipped: int = 0
    waiting: int = 0
    deferred: bool = False  # stopped early because the queue was full


@dataclass
class InboxStatus:
    enabled: bool
    path: str = ""
    owner_email: str = ""
    running: bool = False
    last_scan_at: datetime | None = None
    last_error: str = ""
    imported_total: int = 0
    waiting: int = 0


@dataclass
class _Candidate:
    path: Path
    key: str
    size: int
    mtime_ns: int


def _is_ignored(relative: Path) -> bool:
    if any(part.startswith(".") for part in relative.parts):
        return True
    return relative.name.lower().endswith(_TEMP_SUFFIXES)


def iter_candidates(root: Path) -> Iterator[_Candidate]:
    """Files under ``root`` Mathom could import, in a stable order."""
    allowed = get_settings().allowed_extensions
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            relative = path.relative_to(root)
            if _is_ignored(relative) or path.suffix.lower() not in allowed:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if not path.is_file():
                continue
            yield _Candidate(path, relative.as_posix(), stat.st_size, stat.st_mtime_ns)


def resolve_owner(session: Session) -> int | None:
    """The user imported Mathoms belong to (``None`` in single-user mode)."""
    settings = get_settings()
    if not settings.auth_enabled:
        return None
    email = settings.inbox_owner_email.strip().lower()
    if not email:
        raise InboxConfigError(
            "MATHOM_INBOX_OWNER_EMAIL must name an account when sign-in is enabled."
        )
    user = session.scalars(select(User).where(func.lower(User.email) == email)).first()
    if user is None or not user.is_active:
        raise InboxConfigError(f"No active account for MATHOM_INBOX_OWNER_EMAIL ({email}).")
    return user.id


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(ingest.CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _read_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while chunk := handle.read(ingest.CHUNK_SIZE):
            yield chunk


def _record(
    session: Session, candidate: _Candidate, sha256: str, outcome: str, mathom_id: int | None
) -> None:
    entry = session.scalars(
        select(IngestLedgerEntry).where(IngestLedgerEntry.path == candidate.key)
    ).first()
    if entry is None:
        entry = IngestLedgerEntry(path=candidate.key)
        session.add(entry)
    entry.sha256 = sha256
    entry.size = candidate.size
    entry.mtime_ns = candidate.mtime_ns
    entry.outcome = outcome
    entry.mathom_id = mathom_id
    entry.created_at = datetime.now(UTC)
    session.commit()


def import_file(session: Session, candidate: _Candidate, user_id: int | None) -> str:
    """Import one settled file. Returns the ledger outcome recorded.

    Raises ``ingest.IngestError`` (503) when the queue is full, without
    recording anything, so the file is retried on a later scan.
    """
    settings = get_settings()
    if candidate.size > ingest.max_bytes():
        _record(session, candidate, "", "too_large", None)
        return "too_large"
    sha256 = _sha256(candidate.path)
    known = session.scalars(
        select(IngestLedgerEntry).where(IngestLedgerEntry.sha256 == sha256).limit(1)
    ).first()
    if known is not None:
        # Same bytes seen before (another name, or this file merely touched):
        # keep the earlier verdict for content Mathom couldn't use.
        outcome = known.outcome if known.outcome in ("invalid", "too_large") else "duplicate"
        _record(session, candidate, sha256, outcome, known.mathom_id)
        return outcome
    existing = ingest.find_duplicate(session, user_id, sha256=sha256)
    if existing is not None:
        # Already archived another way (share sheet, API).
        _record(session, candidate, sha256, "duplicate", existing.id)
        return "duplicate"

    ingest.ensure_capacity(session)
    extension = candidate.path.suffix.lower()
    target = ingest.new_audio_path(extension)
    try:
        stored_sha = ingest.write_chunks(target, _read_chunks(candidate.path))
        media = ingest.validate_media(target, extension, analyze_visuals=False)
    except ingest.IngestError as exc:
        outcome = "too_large" if exc.status == 413 else "invalid"
        logger.info("Inbox skipped %s (%s): %s", candidate.key, outcome, exc.detail)
        _record(session, candidate, sha256, outcome, None)
        return outcome
    request = ingest.IngestRequest(
        original_name=candidate.path.name,
        user_id=user_id,
        template_slug=settings.inbox_template,
        template_language=settings.inbox_template_language,
        recorded_at=detect_recorded_at(candidate.path.name, candidate.mtime_ns / 1e9),
    )
    mathom = ingest.create_mathom(session, target, request, media, stored_sha)
    _record(session, candidate, sha256, "imported", mathom.id)
    logger.info("Inbox imported %s as Mathom %s", candidate.key, mathom.id)
    return "imported"


@dataclass
class InboxWatcher:
    """Background thread that scans the inbox folder on a fixed interval."""

    _thread: threading.Thread | None = None
    _stop: threading.Event = field(default_factory=threading.Event)
    _wake: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # Size/mtime seen on the previous scan, per not-yet-handled path.
    _pending: dict[str, tuple[int, int]] = field(default_factory=dict)
    last_scan_at: datetime | None = None
    last_error: str = ""

    def start(self) -> None:
        if get_settings().inbox_path is None:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="mathom-inbox", daemon=True)
        self._thread.start()
        logger.info("Watching %s for new recordings", get_settings().inbox_path)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def wake(self) -> None:
        self._wake.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception:  # noqa: BLE001 — never let one bad scan kill the watcher
                logger.exception("Inbox scan failed")
                self.last_error = "The last scan failed unexpectedly; see the server log."
            self._wake.wait(timeout=get_settings().inbox_poll_seconds)
            self._wake.clear()

    def scan_once(self) -> ScanResult:
        """One pass over the folder. Safe to call directly (tests, "scan now")."""
        with self._lock:
            return self._scan()

    def _scan(self) -> ScanResult:
        result = ScanResult()
        root = get_settings().inbox_path
        self.last_scan_at = datetime.now(UTC)
        if root is None:
            return result
        if not root.is_dir():
            self._fail(f"The inbox folder {root} does not exist or is not mounted.")
            return result
        with get_session_factory()() as session:
            try:
                user_id = resolve_owner(session)
            except InboxConfigError as exc:
                self._fail(f"Inbox paused: {exc}")
                return result
            handled = {
                path: (size, mtime)
                for path, size, mtime in session.execute(
                    select(
                        IngestLedgerEntry.path, IngestLedgerEntry.size, IngestLedgerEntry.mtime_ns
                    )
                ).all()
            }
            seen_now: dict[str, tuple[int, int]] = {}
            imported_any = False
            for candidate in iter_candidates(root):
                signature = (candidate.size, candidate.mtime_ns)
                if handled.get(candidate.key) == signature:
                    continue
                if self._pending.get(candidate.key) != signature:
                    # New or still changing: look again on the next scan.
                    seen_now[candidate.key] = signature
                    result.waiting += 1
                    continue
                if result.deferred:
                    seen_now[candidate.key] = signature
                    result.waiting += 1
                    continue
                try:
                    outcome = import_file(session, candidate, user_id)
                except ingest.IngestError as exc:
                    if exc.status != 503:
                        raise
                    result.deferred = True
                    seen_now[candidate.key] = signature
                    result.waiting += 1
                    continue
                except OSError as exc:
                    logger.warning("Inbox could not read %s: %s", candidate.key, exc)
                    seen_now[candidate.key] = signature
                    result.waiting += 1
                    continue
                if outcome == "imported":
                    result.imported += 1
                    imported_any = True
                else:
                    result.skipped += 1
            self._pending = seen_now
        if imported_any:
            worker.notify()
        self.last_error = ""
        return result

    def _fail(self, message: str) -> None:
        # Log a problem once, not on every poll while it persists.
        if message != self.last_error:
            logger.error(message)
        self.last_error = message

    def status(self, session: Session) -> InboxStatus:
        settings = get_settings()
        root = settings.inbox_path
        if root is None:
            return InboxStatus(enabled=False)
        imported = session.scalar(
            select(func.count())
            .select_from(IngestLedgerEntry)
            .where(IngestLedgerEntry.outcome == "imported")
        )
        return InboxStatus(
            enabled=True,
            path=str(root),
            owner_email=settings.inbox_owner_email if settings.auth_enabled else "",
            running=self.running,
            last_scan_at=self.last_scan_at,
            last_error=self.last_error,
            imported_total=int(imported or 0),
            waiting=len(self._pending),
        )


# Process-wide singleton; started/stopped by the app lifespan.
inbox_watcher = InboxWatcher()
