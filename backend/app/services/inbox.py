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

Ownership: in single-user mode the whole tree is the local user's. With
sign-in enabled, each top-level folder is one person's — ``<inbox>/alice/…``
belongs to the user whose ``inbox_name`` is ``alice`` (see
``services/inbox_names.py``). Files directly in the inbox, and folders that
match no active account, are left alone and reported on the Automation page.

Imported recordings get an AI-written title, ``recorded_at`` guessed from the
filename/mtime, and the origin tag (WhatsApp, Telegram, …).
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
from app.services import inbox_names, ingest
from app.services.source_app import detect_recorded_at
from app.services.worker import worker

logger = logging.getLogger("mathom.inbox")

_TEMP_SUFFIXES = (".tmp", ".part", ".crdownload", ".partial", "~")


@dataclass
class ScanResult:
    imported: int = 0
    skipped: int = 0
    waiting: int = 0
    deferred: bool = False  # stopped early because the queue was full


@dataclass
class InboxFolder:
    """One user's subfolder, as the admin view lists it."""

    name: str
    user: str
    present: bool
    imported: int = 0


@dataclass
class InboxStatus:
    enabled: bool
    path: str = ""
    # True with sign-in enabled: one subfolder per user.
    per_user: bool = False
    running: bool = False
    last_scan_at: datetime | None = None
    last_error: str = ""
    imported_total: int = 0
    waiting: int = 0
    folders: list[InboxFolder] = field(default_factory=list)
    # Top-level folders that match no active account's folder name.
    unmatched_folders: list[str] = field(default_factory=list)
    # Media files lying directly in the inbox (not in anyone's folder).
    loose_files: int = 0


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


def iter_candidates(root: Path, base: Path | None = None) -> Iterator[_Candidate]:
    """Files under ``root`` Mathom could import, in a stable order. Ledger keys
    are relative to ``base`` (default ``root``)."""
    allowed = get_settings().allowed_extensions
    base = base or root
    # os.walk does not descend into symlinked directories.
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            relative = path.relative_to(base)
            if _is_ignored(relative) or path.suffix.lower() not in allowed:
                continue
            # Symlinks are skipped so a link in a synced folder can never make
            # Mathom read a file from elsewhere in the container.
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if not path.is_file():
                continue
            yield _Candidate(path, relative.as_posix(), stat.st_size, stat.st_mtime_ns)


@dataclass
class _Layout:
    """Who owns what in the inbox for this scan."""

    # (folder to walk, owner user id)
    roots: list[tuple[Path, int | None]]
    unmatched_folders: list[str] = field(default_factory=list)
    loose_files: int = 0


def _is_media(path: Path) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and not _is_ignored(Path(path.name))
        and path.suffix.lower() in get_settings().allowed_extensions
    )


def layout(session: Session, root: Path) -> _Layout:
    """Map the inbox to owners. Single-user mode: the whole tree is local."""
    if not get_settings().auth_enabled:
        return _Layout(roots=[(root, None)])
    owners = inbox_names.active_owners(session)
    result = _Layout(roots=[])
    for entry in sorted(root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and not entry.is_symlink():
            owner = owners.get(entry.name.lower())
            if owner is None:
                result.unmatched_folders.append(entry.name)
            else:
                result.roots.append((entry, owner))
        elif _is_media(entry):
            result.loose_files += 1
    return result


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
    session: Session,
    candidate: _Candidate,
    user_id: int | None,
    sha256: str,
    outcome: str,
    mathom_id: int | None,
) -> None:
    entry = session.scalars(
        select(IngestLedgerEntry).where(IngestLedgerEntry.path == candidate.key)
    ).first()
    if entry is None:
        entry = IngestLedgerEntry(path=candidate.key)
        session.add(entry)
    entry.user_id = user_id
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
        _record(session, candidate, user_id, "", "too_large", None)
        return "too_large"
    sha256 = _sha256(candidate.path)
    owner = (
        IngestLedgerEntry.user_id.is_(None)
        if user_id is None
        else IngestLedgerEntry.user_id == user_id
    )
    known = session.scalars(
        select(IngestLedgerEntry).where(IngestLedgerEntry.sha256 == sha256, owner).limit(1)
    ).first()
    if known is not None:
        # Same bytes seen before (another name, or this file merely touched):
        # keep the earlier verdict for content Mathom couldn't use.
        outcome = known.outcome if known.outcome in ("invalid", "too_large") else "duplicate"
        _record(session, candidate, user_id, sha256, outcome, known.mathom_id)
        return outcome
    existing = ingest.find_duplicate(session, user_id, sha256=sha256)
    if existing is not None:
        # Already archived another way (share sheet, API).
        _record(session, candidate, user_id, sha256, "duplicate", existing.id)
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
        _record(session, candidate, user_id, sha256, outcome, None)
        return outcome
    request = ingest.IngestRequest(
        original_name=candidate.path.name,
        user_id=user_id,
        template_slug=settings.inbox_template,
        template_language=settings.inbox_template_language,
        recorded_at=detect_recorded_at(candidate.path.name, candidate.mtime_ns / 1e9),
    )
    mathom = ingest.create_mathom(session, target, request, media, stored_sha)
    _record(session, candidate, user_id, sha256, "imported", mathom.id)
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
    unmatched_folders: list[str] = field(default_factory=list)
    loose_files: int = 0

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
            plan = layout(session, root)
            self.unmatched_folders = plan.unmatched_folders
            self.loose_files = plan.loose_files
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
            for folder, user_id in plan.roots:
                imported_any |= self._scan_folder(
                    session, folder, root, user_id, handled, seen_now, result
                )
            self._pending = seen_now
        if imported_any:
            worker.notify()
        self.last_error = ""
        return result

    def _scan_folder(
        self,
        session: Session,
        folder: Path,
        root: Path,
        user_id: int | None,
        handled: dict[str, tuple[int, int]],
        seen_now: dict[str, tuple[int, int]],
        result: ScanResult,
    ) -> bool:
        imported_any = False
        for candidate in iter_candidates(folder, base=root):
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
        return imported_any

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
        counts: dict[int | None, int] = {
            user_id: int(count)
            for user_id, count in session.execute(
                select(IngestLedgerEntry.user_id, func.count())
                .where(IngestLedgerEntry.outcome == "imported")
                .group_by(IngestLedgerEntry.user_id)
            ).all()
        }
        folders: list[InboxFolder] = []
        if settings.auth_enabled:
            inbox_names.ensure_all(session)
            users = session.scalars(
                select(User).where(User.is_active.is_(True)).order_by(User.inbox_name)
            ).all()
            folders = [
                InboxFolder(
                    name=user.inbox_name or "",
                    user=user.name or user.email,
                    present=(root / (user.inbox_name or "")).is_dir(),
                    imported=int(counts.get(user.id, 0)),
                )
                for user in users
            ]
        return InboxStatus(
            enabled=True,
            path=str(root),
            per_user=settings.auth_enabled,
            running=self.running,
            last_scan_at=self.last_scan_at,
            last_error=self.last_error,
            imported_total=int(sum(counts.values())),
            waiting=len(self._pending),
            folders=folders,
            unmatched_folders=list(self.unmatched_folders),
            loose_files=self.loose_files,
        )

    def folder_for(self, session: Session, user: User | None) -> tuple[str, int]:
        """(container path, imported count) of the folder ``user`` should fill."""
        root = get_settings().inbox_path
        if root is None:
            return "", 0
        owner = (
            IngestLedgerEntry.user_id.is_(None)
            if user is None
            else IngestLedgerEntry.user_id == user.id
        )
        imported = session.scalar(
            select(func.count())
            .select_from(IngestLedgerEntry)
            .where(IngestLedgerEntry.outcome == "imported", owner)
        )
        if user is None or not get_settings().auth_enabled:
            return str(root), int(imported or 0)
        inbox_names.ensure_all(session)
        return str(root / (user.inbox_name or "")), int(imported or 0)


# Process-wide singleton; started/stopped by the app lifespan.
inbox_watcher = InboxWatcher()
