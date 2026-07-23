"""Tag colours and the source-origin auto-tagging.

This folds a recording's detected origin (WhatsApp, Telegram, …) into the shared
tag system: instead of a separate "source" concept, each origin becomes an
auto-managed ``kind="source"`` tag that users filter and manage like any other.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Mathom, Tag

# The palette a tag colour may use. Mirrored in frontend/src/lib/tagColor.ts —
# the two lists must stay in agreement so every stored token renders.
TAG_COLORS: tuple[str, ...] = (
    "moss",
    "hearth",
    "ochre",
    "clay",
    "rose",
    "plum",
    "indigo",
    "teal",
    "stone",
)
# New manual tags default to the moss green that anchors the palette.
DEFAULT_TAG_COLOR = "moss"
# Auto-applied origin tags read as "system": a single, quieter stone colour.
SOURCE_TAG_COLOR = "stone"


def _find_owned_tag(db: Session, name: str, user_id: int | None) -> Tag | None:
    """Look up a tag by name within one owner's vocabulary (NULL = unowned)."""
    stmt = select(Tag).where(Tag.name == name)
    stmt = stmt.where(Tag.user_id.is_(None) if user_id is None else Tag.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def apply_source_tag(db: Session, mathom: Mathom) -> None:
    """Attach an auto-managed tag for the recording's detected origin app.

    A no-op when the origin is unknown. Reuses an existing tag of the same name
    so a manual tag and its source twin never diverge. The caller commits.
    """
    if not mathom.source_app:
        return
    name = mathom.source_app.strip().lower()
    if not name:
        return
    tag = _find_owned_tag(db, name, mathom.user_id)
    if tag is None:
        tag = Tag(name=name, color=SOURCE_TAG_COLOR, kind="source", user_id=mathom.user_id)
        db.add(tag)
    if tag not in mathom.tags:
        mathom.tags.append(tag)
