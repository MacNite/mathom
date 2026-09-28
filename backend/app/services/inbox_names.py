"""Per-user folder names inside the watched folder.

With sign-in enabled, ``<inbox>/<inbox_name>/…`` belongs to the user with that
``inbox_name``. Names are lowercase and filesystem-safe, unique across users,
assigned automatically from the display name (``Alice Baker`` → ``alice-baker``)
and editable by the user.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

MAX_LENGTH = 48
_VALID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")


class InboxNameError(ValueError):
    """A name that is malformed or already taken."""


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9._-]+", "-", ascii_text.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-._")
    return slug[:MAX_LENGTH].rstrip("-._")


def validate(raw: str) -> str:
    name = raw.strip().lower()
    if not _VALID.fullmatch(name):
        raise InboxNameError(
            "Use 1–48 lowercase letters, digits, dots, dashes or underscores, "
            "starting with a letter or digit."
        )
    return name


def _taken(session: Session, name: str, except_user: int | None = None) -> bool:
    query = select(User.id).where(User.inbox_name == name)
    if except_user is not None:
        query = query.where(User.id != except_user)
    return session.scalar(query.limit(1)) is not None


def suggest(session: Session, user: User) -> str:
    """A free name for ``user``, based on their display name."""
    base = slugify(user.name) or f"user-{user.id}"
    candidate, counter = base, 2
    while _taken(session, candidate, except_user=user.id):
        suffix = f"-{counter}"
        candidate = f"{base[: MAX_LENGTH - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def ensure_all(session: Session) -> None:
    """Give every user without a folder name one (new accounts, upgrades)."""
    missing = session.scalars(select(User).where(User.inbox_name.is_(None))).all()
    for user in missing:
        user.inbox_name = suggest(session, user)
        session.flush()
    if missing:
        session.commit()


def rename(session: Session, user: User, raw: str) -> str:
    name = validate(raw)
    if _taken(session, name, except_user=user.id):
        raise InboxNameError("Another account already uses that folder name.")
    user.inbox_name = name
    session.commit()
    return name


def active_owners(session: Session) -> dict[str, int]:
    """Folder name → user id, for every active account."""
    ensure_all(session)
    rows = session.execute(select(User.inbox_name, User.id).where(User.is_active.is_(True))).all()
    return {name: user_id for name, user_id in rows if name}
