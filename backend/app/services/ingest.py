"""Turn a media file into a queued Mathom — the one path every way in shares.

The browser upload, the token-authenticated ingest API and the watched folder
all end here: check capacity and extension, validate the streams with
ffprobe, create the row (with its origin tag), and enqueue processing. Callers
only differ in how the bytes arrive and who the owner is.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Mathom, Tag
from app.services import jobs, transcription, vision
from app.services.source_app import detect_source_app
from app.services.tags import DEFAULT_TAG_COLOR, apply_source_tag

logger = logging.getLogger("mathom.ingest")

UNTITLED = "Untitled Mathom"
_VIDEO_EXTENSIONS = {".mp4", ".webm"}


class IngestError(Exception):
    """A request the caller should see as an HTTP error (status + calm detail)."""

    def __init__(self, status: int, detail: str, headers: dict[str, str] | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.headers = headers


@dataclass
class IngestRequest:
    original_name: str
    user_id: int | None = None
    # Blank means "let the pipeline write a title" (see ``UNTITLED``) unless
    # ``title_from_filename`` asks for the filename stem, as the upload
    # dialog always has.
    title: str = ""
    title_from_filename: bool = False
    speaker: str = ""
    template_slug: str = "general-summary"
    template_language: str = "en"
    analyze_visuals: bool = False
    source_app: str | None = None
    recorded_at: datetime | None = None
    external_source: str | None = None
    external_id: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaInfo:
    has_audio: bool
    has_video: bool
    duration: float | None


def ensure_capacity(session: Session) -> None:
    if jobs.queued_count(session) >= get_settings().max_queued_jobs:
        raise IngestError(
            503,
            "Processing queue is full. Please try again once a recording has finished.",
            {"Retry-After": "60"},
        )


def check_extension(original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    if extension not in get_settings().allowed_extensions:
        raise IngestError(415, f"Unsupported audio format '{extension or 'unknown'}'")
    return extension


def new_audio_path(extension: str) -> Path:
    """A fresh, server-generated storage path; the original name is never used."""
    settings = get_settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    return settings.audio_dir / f"{uuid.uuid4().hex}{extension}"


def max_bytes() -> int:
    return get_settings().max_upload_mb * 1024 * 1024


def too_large() -> IngestError:
    return IngestError(413, f"File exceeds the {get_settings().max_upload_mb} MB upload limit")


def write_chunks(target: Path, chunks: Iterable[bytes]) -> str:
    """Stream ``chunks`` to ``target`` enforcing the size limit; return the
    SHA-256. The partial file is removed on any failure."""
    digest = hashlib.sha256()
    written = 0
    limit = max_bytes()
    try:
        with target.open("wb") as out:
            for chunk in chunks:
                written += len(chunk)
                if written > limit:
                    raise too_large()
                digest.update(chunk)
                out.write(chunk)
        if written == 0:
            raise IngestError(400, "Uploaded file is empty")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def validate_media(target: Path, extension: str, analyze_visuals: bool) -> MediaInfo:
    """Classify the stored file with ffprobe. Deletes it and raises
    ``IngestError`` when it is not something Mathom can process."""
    settings = get_settings()
    try:
        # Ordinary audio keeps the established validation path. Potential
        # videos (and every visual-analysis request) are stream-classified.
        if extension not in _VIDEO_EXTENSIONS and not analyze_visuals:
            transcription.validate_audio(target)
            info = MediaInfo(True, False, None)
        else:
            has_audio, has_video, duration = vision.media_streams(target)
            info = MediaInfo(has_audio, has_video, duration)
        if not info.has_audio and not info.has_video:
            raise vision.VisionError("No usable media streams")
        if analyze_visuals and not info.has_video:
            raise IngestError(422, "Visual analysis is only available for videos")
        if analyze_visuals and not settings.vision_enabled:
            raise IngestError(409, "Visual analysis is disabled by this server")
        if info.has_video and not info.has_audio and not analyze_visuals:
            raise IngestError(422, "A video without audio requires visual analysis")
    except (vision.VisionError, transcription.AudioValidationError) as exc:
        target.unlink(missing_ok=True)
        raise IngestError(422, "File has no usable audio or video stream") from exc
    except IngestError:
        target.unlink(missing_ok=True)
        raise
    return info


def find_duplicate(
    session: Session,
    user_id: int | None,
    *,
    external_source: str | None = None,
    external_id: str | None = None,
    sha256: str | None = None,
) -> Mathom | None:
    """An existing Mathom of this owner for the same message or file."""
    owner = Mathom.user_id.is_(None) if user_id is None else Mathom.user_id == user_id
    if external_source and external_id:
        found = session.scalars(
            select(Mathom)
            .where(
                owner,
                Mathom.external_source == external_source,
                Mathom.external_id == external_id,
            )
            .limit(1)
        ).first()
        if found is not None:
            return found
    if sha256:
        return session.scalars(
            select(Mathom).where(owner, Mathom.content_sha256 == sha256).limit(1)
        ).first()
    return None


def _apply_tags(session: Session, mathom: Mathom, names: Iterable[str]) -> None:
    for raw in names:
        name = raw.strip().lower()[:100]
        if not name:
            continue
        owner = Tag.user_id.is_(None) if mathom.user_id is None else Tag.user_id == mathom.user_id
        tag = session.scalars(select(Tag).where(Tag.name == name, owner)).first()
        if tag is None:
            tag = Tag(name=name, color=DEFAULT_TAG_COLOR, kind="manual", user_id=mathom.user_id)
            session.add(tag)
        if tag not in mathom.tags:
            mathom.tags.append(tag)


def _title(request: IngestRequest) -> str:
    if request.title.strip():
        return request.title.strip()[:300]
    if request.title_from_filename:
        return Path(request.original_name).stem[:300] or UNTITLED
    return UNTITLED


def create_mathom(
    session: Session,
    target: Path,
    request: IngestRequest,
    media: MediaInfo,
    sha256: str | None = None,
) -> Mathom:
    """Insert the Mathom for an already stored and validated file and queue
    its processing. The caller wakes the worker (``worker.notify()``)."""
    settings = get_settings()
    analyze = request.analyze_visuals
    mathom = Mathom(
        title=_title(request),
        speaker=request.speaker.strip()[:200] or None,
        source_app=(request.source_app or "").strip()[:50]
        or detect_source_app(request.original_name),
        original_filename=request.original_name[:500],
        audio_path=str(target),
        source_path=str(target) if media.has_video else "",
        source_type="video" if media.has_video else "audio",
        duration_seconds=media.duration,
        has_audio_stream=media.has_audio,
        has_video_stream=media.has_video,
        vision_requested=analyze,
        vision_status="pending" if analyze else "not_requested",
        vision_model=settings.vision_model if analyze else None,
        status="pending",
        template_language=request.template_language,
        user_id=request.user_id,
        recorded_at=request.recorded_at,
        content_sha256=sha256,
        external_source=request.external_source,
        external_id=request.external_id,
    )
    session.add(mathom)
    # Fold the detected origin into the shared tag system before the row is
    # committed, so the recording is filterable by source from the first render.
    apply_source_tag(session, mathom)
    _apply_tags(session, mathom, request.tags)
    session.commit()
    session.refresh(mathom)
    # Durable: the job survives a restart and is picked up by the worker.
    jobs.enqueue(session, mathom.id, request.template_slug)
    return mathom
