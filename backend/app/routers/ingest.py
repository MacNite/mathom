"""Automated ingest: token-authenticated uploads and the watched-folder status.

Two upload shapes, so every automation tool has one it can speak:

- ``POST /ingest/audio`` — multipart form (curl ``-F``, iOS Shortcuts "Form").
- ``POST /ingest/audio/raw?filename=…`` — the file as the raw request body
  (Tasker's HTTP Request "File To Send").

Both are idempotent for automation: resending the same message ID (or the
same bytes) returns the existing Mathom with ``200`` and
``X-Mathom-Duplicate: true`` instead of creating another.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user, ingest_user, require_admin_when_auth_enabled
from app.models import Mathom, User
from app.schemas import InboxStatusOut, MathomOut, MyInboxFolderOut, MyInboxFolderUpdate
from app.services import inbox_names, ingest
from app.services.inbox import inbox_watcher

router = APIRouter(prefix="/ingest", tags=["ingest"])

_LANG = r"^(en|de|es)$"


def _request(
    user: User | None,
    *,
    filename: str,
    title: str,
    speaker: str,
    template_slug: str,
    template_language: str,
    source_app: str,
    external_source: str,
    external_id: str,
    recorded_at: datetime | None,
    tags: str,
) -> ingest.IngestRequest:
    external_id = external_id.strip()[:200]
    return ingest.IngestRequest(
        original_name=filename or "recording",
        user_id=user.id if user else None,
        title=title,
        speaker=speaker,
        template_slug=template_slug or "general-summary",
        template_language=template_language,
        source_app=source_app or None,
        recorded_at=recorded_at,
        external_source=(external_source.strip()[:50] or "api") if external_id else None,
        external_id=external_id or None,
        tags=tuple(tag for tag in tags.split(",") if tag.strip()),
    )


async def _run(
    db: Session, chunks: AsyncIterator[bytes], request: ingest.IngestRequest, response: Response
) -> Mathom:
    try:
        mathom, created = await ingest.ingest_stream(db, chunks, request, dedupe=True)
    except ingest.IngestError as exc:
        raise HTTPException(exc.status, exc.detail, headers=exc.headers) from exc
    if not created:
        response.status_code = 200
        response.headers["X-Mathom-Duplicate"] = "true"
    return mathom


@router.post("/audio", response_model=MathomOut, status_code=201)
async def ingest_audio(
    response: Response,
    file: UploadFile,
    title: str = Form(default="", max_length=300),
    speaker: str = Form(default="", max_length=200),
    template_slug: str = Form(default="general-summary", max_length=100),
    template_language: str = Form(default="en", pattern=_LANG),
    source_app: str = Form(default="", max_length=50),
    external_source: str = Form(default="", max_length=50),
    external_id: str = Form(default="", max_length=200),
    recorded_at: datetime | None = Form(default=None),
    tags: str = Form(default="", max_length=500),
    db: Session = Depends(get_db),
    user: User | None = Depends(ingest_user),
) -> Mathom:
    request = _request(
        user,
        filename=file.filename or "",
        title=title,
        speaker=speaker,
        template_slug=template_slug,
        template_language=template_language,
        source_app=source_app,
        external_source=external_source,
        external_id=external_id,
        recorded_at=recorded_at,
        tags=tags,
    )
    return await _run(db, ingest.upload_chunks(file), request, response)


@router.post("/audio/raw", response_model=MathomOut, status_code=201)
async def ingest_audio_raw(
    http_request: Request,
    response: Response,
    filename: str = Query(min_length=1, max_length=500),
    title: str = Query(default="", max_length=300),
    speaker: str = Query(default="", max_length=200),
    template_slug: str = Query(default="general-summary", max_length=100),
    template_language: str = Query(default="en", pattern=_LANG),
    source_app: str = Query(default="", max_length=50),
    external_source: str = Query(default="", max_length=50),
    external_id: str = Query(default="", max_length=200),
    recorded_at: datetime | None = Query(default=None),
    tags: str = Query(default="", max_length=500),
    db: Session = Depends(get_db),
    user: User | None = Depends(ingest_user),
) -> Mathom:
    declared = http_request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > ingest.max_bytes():
        exc = ingest.too_large()
        raise HTTPException(exc.status, exc.detail)
    request = _request(
        user,
        # Only the extension of the caller's name is trusted (storage names
        # are server-generated); strip any path it carries.
        filename=filename.replace("\\", "/").rsplit("/", 1)[-1],
        title=title,
        speaker=speaker,
        template_slug=template_slug,
        template_language=template_language,
        source_app=source_app,
        external_source=external_source,
        external_id=external_id,
        recorded_at=recorded_at,
        tags=tags,
    )
    return await _run(db, http_request.stream(), request, response)


@router.get("/inbox", response_model=InboxStatusOut)
def inbox_status(
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin_when_auth_enabled),
) -> InboxStatusOut:
    status = inbox_watcher.status(db)
    return InboxStatusOut.model_validate(status, from_attributes=True)


@router.post("/inbox/scan", status_code=202)
def inbox_scan_now(_admin: User | None = Depends(require_admin_when_auth_enabled)) -> Response:
    if not inbox_watcher.running:
        raise HTTPException(status_code=409, detail="The watched folder is not enabled")
    inbox_watcher.wake()
    return Response(status_code=202)


def _my_folder(db: Session, user: User | None) -> MyInboxFolderOut:
    settings = get_settings()
    if settings.inbox_path is None:
        return MyInboxFolderOut(enabled=False)
    path, imported = inbox_watcher.folder_for(db, user)
    per_user = settings.auth_enabled and user is not None
    return MyInboxFolderOut(
        enabled=True,
        per_user=per_user,
        inbox_name=user.inbox_name if per_user and user is not None else None,
        path=path,
        present=Path(path).is_dir(),
        imported=imported,
    )


@router.get("/inbox/me", response_model=MyInboxFolderOut)
def my_inbox_folder(
    db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> MyInboxFolderOut:
    return _my_folder(db, user)


@router.put("/inbox/me", response_model=MyInboxFolderOut)
def rename_my_inbox_folder(
    payload: MyInboxFolderUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> MyInboxFolderOut:
    if user is None:
        raise HTTPException(
            status_code=409, detail="Without sign-in the whole watched folder is yours"
        )
    try:
        inbox_names.rename(db, user, payload.inbox_name)
    except inbox_names.InboxNameError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _my_folder(db, user)
