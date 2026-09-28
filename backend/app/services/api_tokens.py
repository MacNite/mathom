"""Personal access tokens for automated uploads.

Tokens look like ``mth_<43 url-safe chars>`` (256 bits of randomness). Only a
SHA-256 digest is stored — a fast hash is appropriate because the secret is
high-entropy, not a password — and the plaintext is returned once.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.models import ApiToken

TOKEN_PREFIX = "mth_"
SCOPE_INGEST = "ingest"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _owner(user_id: int | None) -> ColumnElement[bool]:
    return ApiToken.user_id.is_(None) if user_id is None else ApiToken.user_id == user_id


def create(
    session: Session, user_id: int | None, name: str, expires_in_days: int | None
) -> tuple[ApiToken, str]:
    plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token = ApiToken(
        user_id=user_id,
        name=name.strip()[:100],
        token_hash=_digest(plaintext),
        prefix=plaintext[:12],
        scope=SCOPE_INGEST,
        expires_at=(
            datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None
        ),
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    return token, plaintext


def list_for(session: Session, user_id: int | None) -> list[ApiToken]:
    return list(
        session.scalars(
            select(ApiToken).where(_owner(user_id)).order_by(ApiToken.created_at.desc())
        ).all()
    )


def delete(session: Session, user_id: int | None, token_id: int) -> bool:
    token = session.scalars(
        select(ApiToken).where(ApiToken.id == token_id, _owner(user_id))
    ).first()
    if token is None:
        return False
    session.delete(token)
    session.commit()
    return True


def _aware(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; they were stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def authenticate(session: Session, plaintext: str, scope: str = SCOPE_INGEST) -> ApiToken | None:
    """The live token for ``plaintext``, or ``None``. Records its last use."""
    if not plaintext.startswith(TOKEN_PREFIX) or len(plaintext) > 200:
        return None
    token = session.scalars(
        select(ApiToken).where(ApiToken.token_hash == _digest(plaintext))
    ).first()
    if token is None or token.scope != scope:
        return None
    now = datetime.now(UTC)
    if token.expires_at is not None and _aware(token.expires_at) <= now:
        return None
    token.last_used_at = now
    session.commit()
    return token
