"""Full-text search (FTS5), tag listing, and the archive timeline."""

import re

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, owned_filter, owns
from app.models import Mathom, User
from app.schemas import MathomListItem, SearchHit, TimelineBucket

router = APIRouter(tags=["search"])

_TOKEN = re.compile(r"[\wÀ-ɏ]+")


def _fts_query(raw: str) -> str | None:
    """Build a safe FTS5 prefix query from raw user input."""
    tokens = _TOKEN.findall(raw)[:12]
    if not tokens:
        return None
    return " ".join(f'"{token}"*' for token in tokens)


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str,
    limit: int = 30,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[SearchHit]:
    match = _fts_query(q)
    if match is None:
        return []
    # Over-fetch a little, then drop rows the current user does not own. The FTS
    # index has no user column, so ownership is enforced on the resolved rows.
    rows = db.execute(
        text(
            "SELECT rowid, snippet(mathom_fts, -1, '<mark>', '</mark>', ' … ', 16) "
            "FROM mathom_fts WHERE mathom_fts MATCH :match ORDER BY rank LIMIT :limit"
        ),
        {"match": match, "limit": min(limit, 100) * (3 if user else 1)},
    ).all()
    hits: list[SearchHit] = []
    for rowid, snippet in rows:
        mathom = db.get(Mathom, rowid)
        if mathom is None or not owns(mathom, user):
            continue
        hits.append(SearchHit(mathom=MathomListItem.model_validate(mathom), snippet=snippet or ""))
        if len(hits) >= min(limit, 100):
            break
    return hits


@router.get("/timeline", response_model=list[TimelineBucket])
def timeline(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[TimelineBucket]:
    rows = db.execute(
        select(
            func.strftime("%Y-%m", Mathom.created_at).label("month"),
            func.count(Mathom.id),
        )
        .where(owned_filter(Mathom, user))
        .group_by("month")
        .order_by(text("month DESC"))
    ).all()
    return [TimelineBucket(month=month, count=count) for month, count in rows if month]
