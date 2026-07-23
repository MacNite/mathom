"""User tag vocabulary: list with usage counts, create, rename, recolour,
delete, and merge. Per-user scoped; ``source`` (origin) tags are managed
automatically and cannot be renamed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, owned_filter, owns
from app.models import Tag, User, mathom_tags
from app.schemas import TagCreate, TagMerge, TagOut, TagUpdate
from app.services.tags import DEFAULT_TAG_COLOR, TAG_COLORS

router = APIRouter(prefix="/tags", tags=["tags"])


def _validate_color(color: str) -> str:
    if color not in TAG_COLORS:
        raise HTTPException(status_code=422, detail="Unknown tag colour")
    return color


def _get_owned_tag(tag_id: int, db: Session, user: User | None) -> Tag:
    tag = db.get(Tag, tag_id)
    # Report not-owned rows as 404 so existence never leaks across users.
    if tag is None or not owns(tag, user):
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


def _as_out(tag: Tag, count: int) -> TagOut:
    return TagOut(id=tag.id, name=tag.name, color=tag.color, kind=tag.kind, mathom_count=count)


@router.get("", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[TagOut]:
    query = (
        select(Tag, func.count(mathom_tags.c.mathom_id))
        .outerjoin(mathom_tags, mathom_tags.c.tag_id == Tag.id)
        .where(owned_filter(Tag, user))
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    return [_as_out(tag, count) for tag, count in db.execute(query).all()]


@router.post("", response_model=TagOut, status_code=201)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> TagOut:
    name = payload.name.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name cannot be empty")
    color = _validate_color(payload.color) if payload.color else DEFAULT_TAG_COLOR
    existing = db.execute(
        select(Tag).where(Tag.name == name, owned_filter(Tag, user))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A tag with that name already exists")
    tag = Tag(name=name, color=color, kind="manual", user_id=user.id if user else None)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _as_out(tag, 0)


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> TagOut:
    tag = _get_owned_tag(tag_id, db, user)
    data = payload.model_dump(exclude_unset=True)
    if data.get("color") is not None:
        tag.color = _validate_color(data["color"])
    if data.get("name") is not None:
        if tag.kind == "source":
            raise HTTPException(
                status_code=400,
                detail="Source tags are managed automatically and cannot be renamed",
            )
        new_name = data["name"].strip().lower()
        if not new_name:
            raise HTTPException(status_code=400, detail="Tag name cannot be empty")
        if new_name != tag.name:
            clash = db.execute(
                select(Tag).where(Tag.name == new_name, owned_filter(Tag, user), Tag.id != tag.id)
            ).scalar_one_or_none()
            if clash is not None:
                raise HTTPException(status_code=409, detail="A tag with that name already exists")
            tag.name = new_name
    db.commit()
    db.refresh(tag)
    return _as_out(tag, len(tag.mathoms))


@router.delete("/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    tag = _get_owned_tag(tag_id, db, user)
    db.delete(tag)
    db.commit()
    return Response(status_code=204)


@router.post("/{tag_id}/merge", response_model=TagOut)
def merge_tag(
    tag_id: int,
    payload: TagMerge,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> TagOut:
    if payload.into_id == tag_id:
        raise HTTPException(status_code=400, detail="Cannot merge a tag into itself")
    source = _get_owned_tag(tag_id, db, user)
    target = _get_owned_tag(payload.into_id, db, user)
    # Re-tag every recording onto the surviving tag, then drop the source. The
    # membership check keeps recordings already carrying both from duplicating.
    for mathom in list(source.mathoms):
        if target not in mathom.tags:
            mathom.tags.append(target)
    db.delete(source)
    db.commit()
    db.refresh(target)
    return _as_out(target, len(target.mathoms))
