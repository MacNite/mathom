"""Mathom CRUD, upload, audio streaming, summaries, tags, and exports."""

import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, refresh_fts
from app.deps import current_user, owned_filter, owns
from app.models import Mathom, Summary, Tag, User
from app.schemas import (
    MathomListItem,
    MathomOut,
    MathomUpdate,
    SummaryCreate,
    SummaryOut,
    TagCreate,
    TagOut,
)
from app.services import export, jobs, pipeline
from app.services.worker import worker

router = APIRouter(prefix="/mathoms", tags=["mathoms"])

CHUNK_SIZE = 1024 * 1024


def _get_mathom(mathom_id: int, db: Session, user: User | None) -> Mathom:
    mathom = db.get(Mathom, mathom_id)
    # Report not-owned rows as 404 so existence never leaks across users.
    if mathom is None or not owns(mathom, user):
        raise HTTPException(status_code=404, detail="Mathom not found")
    return mathom


@router.get("", response_model=list[MathomListItem])
def list_mathoms(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
    favorite: bool | None = None,
    archived: bool = False,
    tag: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Mathom]:
    query = select(Mathom).where(Mathom.archived == archived, owned_filter(Mathom, user))
    if favorite is not None:
        query = query.where(Mathom.favorite == favorite)
    if status is not None:
        query = query.where(Mathom.status == status)
    if tag is not None:
        query = query.join(Mathom.tags).where(Tag.name == tag)
    query = query.order_by(Mathom.created_at.desc()).limit(min(limit, 500)).offset(offset)
    return list(db.execute(query).scalars().unique())


@router.post("", response_model=MathomOut, status_code=201)
async def upload_mathom(
    file: UploadFile,
    title: str = Form(default=""),
    template_slug: str = Form(default="general-summary"),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Mathom:
    settings = get_settings()
    original_name = file.filename or "recording"
    extension = Path(original_name).suffix.lower()
    if extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio format '{extension or 'unknown'}'",
        )

    stored_name = f"{uuid.uuid4().hex}{extension}"
    target = settings.audio_dir / stored_name
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_mb} MB upload limit",
                    )
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    if written == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    mathom = Mathom(
        title=title.strip() or Path(original_name).stem or "Untitled Mathom",
        original_filename=original_name[:500],
        audio_path=str(target),
        status="pending",
        user_id=user.id if user else None,
    )
    db.add(mathom)
    db.commit()
    db.refresh(mathom)
    # Durable: the job survives a restart and is picked up by the worker.
    jobs.enqueue(db, mathom.id, template_slug)
    worker.notify()
    return mathom


@router.get("/{mathom_id}", response_model=MathomOut)
def get_mathom(
    mathom_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Mathom:
    return _get_mathom(mathom_id, db, user)


@router.patch("/{mathom_id}", response_model=MathomOut)
def update_mathom(
    mathom_id: int,
    payload: MathomUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Mathom:
    mathom = _get_mathom(mathom_id, db, user)
    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(mathom, field, value)
    db.commit()
    if "title" in changed or "transcript" in changed:
        refresh_fts(db, mathom.id)
        db.commit()
    db.refresh(mathom)
    return mathom


@router.delete("/{mathom_id}", status_code=204)
def delete_mathom(
    mathom_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    mathom = _get_mathom(mathom_id, db, user)
    audio_path = Path(mathom.audio_path) if mathom.audio_path else None
    db.delete(mathom)
    db.commit()
    refresh_fts(db, mathom_id)
    db.commit()
    if audio_path is not None:
        audio_path.unlink(missing_ok=True)
    return Response(status_code=204)


@router.get("/{mathom_id}/audio")
def get_audio(
    mathom_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> FileResponse:
    mathom = _get_mathom(mathom_id, db, user)
    path = Path(mathom.audio_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, filename=mathom.original_filename or path.name)


@router.post("/{mathom_id}/summaries", response_model=SummaryOut, status_code=201)
def create_summary(
    mathom_id: int,
    payload: SummaryCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> SummaryOut:
    mathom = _get_mathom(mathom_id, db, user)
    if not mathom.transcript:
        raise HTTPException(status_code=409, detail="Mathom has no transcript yet")
    summary = pipeline.summarize_mathom(mathom_id, payload.template_slug)
    if summary is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return SummaryOut.model_validate(summary)


@router.delete("/{mathom_id}/summaries/{summary_id}", status_code=204)
def delete_summary(
    mathom_id: int,
    summary_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    _get_mathom(mathom_id, db, user)
    summary = db.get(Summary, summary_id)
    if summary is None or summary.mathom_id != mathom_id:
        raise HTTPException(status_code=404, detail="Summary not found")
    db.delete(summary)
    db.commit()
    return Response(status_code=204)


@router.post("/{mathom_id}/tags", response_model=list[TagOut])
def add_tag(
    mathom_id: int,
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[Tag]:
    mathom = _get_mathom(mathom_id, db, user)
    name = payload.name.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name cannot be empty")
    tag = db.execute(
        select(Tag).where(Tag.name == name, owned_filter(Tag, user))
    ).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name, user_id=user.id if user else None)
        db.add(tag)
    if tag not in mathom.tags:
        mathom.tags.append(tag)
    db.commit()
    return mathom.tags


@router.delete("/{mathom_id}/tags/{tag_id}", response_model=list[TagOut])
def remove_tag(
    mathom_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[Tag]:
    mathom = _get_mathom(mathom_id, db, user)
    mathom.tags = [tag for tag in mathom.tags if tag.id != tag_id]
    db.commit()
    return mathom.tags


@router.get("/{mathom_id}/export")
def export_mathom(
    mathom_id: int,
    format: str = "md",
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    mathom = _get_mathom(mathom_id, db, user)
    if format == "md":
        body, media_type, ext = export.to_markdown(mathom), "text/markdown", "md"
    elif format == "txt":
        body, media_type, ext = export.to_text(mathom), "text/plain", "txt"
    elif format == "json":
        body, media_type, ext = export.to_json(mathom), "application/json", "json"
    else:
        raise HTTPException(status_code=400, detail="format must be md, txt, or json")
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in mathom.title)[:60]
    filename = f"mathom-{mathom.id}-{safe_title.strip() or 'export'}.{ext}"
    return Response(
        content=body,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
