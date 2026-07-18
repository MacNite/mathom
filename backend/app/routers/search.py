"""Full-text search (FTS5), tag listing, and the archive timeline."""

import re

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Mathom, Tag
from app.schemas import MathomListItem, SearchHit, TagOut, TimelineBucket

router = APIRouter(tags=["search"])

_TOKEN = re.compile(r"[\wÀ-ɏ]+")


def _fts_query(raw: str) -> str | None:
    """Build a safe FTS5 prefix query from raw user input."""
    tokens = _TOKEN.findall(raw)[:12]
    if not tokens:
        return None
    return " ".join(f'"{token}"*' for token in tokens)


@router.get("/search", response_model=list[SearchHit])
def search(q: str, limit: int = 30, db: Session = Depends(get_db)) -> list[SearchHit]:
    match = _fts_query(q)
    if match is None:
        return []
    rows = db.execute(
        text(
            "SELECT rowid, snippet(mathom_fts, -1, '<mark>', '</mark>', ' … ', 16) "
            "FROM mathom_fts WHERE mathom_fts MATCH :match ORDER BY rank LIMIT :limit"
        ),
        {"match": match, "limit": min(limit, 100)},
    ).all()
    hits: list[SearchHit] = []
    for rowid, snippet in rows:
        mathom = db.get(Mathom, rowid)
        if mathom is None:
            continue
        hits.append(SearchHit(mathom=MathomListItem.model_validate(mathom), snippet=snippet or ""))
    return hits


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db)) -> list[Tag]:
    return list(db.execute(select(Tag).order_by(Tag.name)).scalars())


@router.get("/timeline", response_model=list[TimelineBucket])
def timeline(db: Session = Depends(get_db)) -> list[TimelineBucket]:
    rows = db.execute(
        select(
            func.strftime("%Y-%m", Mathom.created_at).label("month"),
            func.count(Mathom.id),
        )
        .group_by("month")
        .order_by(text("month DESC"))
    ).all()
    return [TimelineBucket(month=month, count=count) for month, count in rows if month]
