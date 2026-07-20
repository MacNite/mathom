"""Session management, OAuth state, and user provisioning.

This module owns the rules that turn an Authentik identity into a Mathom
``User`` (including who becomes the Owner) and the opaque server-side sessions
that back the login cookie.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ROLE_ADMIN,
    ROLE_USER,
    AuthSession,
    Collection,
    Mathom,
    OAuthState,
    Tag,
    User,
)

# OAuth login flows must complete within this window.
_STATE_TTL = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(UTC)


def _token() -> str:
    return secrets.token_urlsafe(32)


# --- OAuth state ------------------------------------------------------------


def create_oauth_state(session: Session, redirect_to: str) -> OAuthState:
    state = OAuthState(state=_token(), nonce=_token(), redirect_to=redirect_to or "/")
    session.add(state)
    session.commit()
    return state


def pop_oauth_state(session: Session, state_value: str) -> OAuthState | None:
    """Consume a state token: returns it once, then deletes it. Expired
    tokens are treated as missing."""
    state = session.execute(
        select(OAuthState).where(OAuthState.state == state_value)
    ).scalar_one_or_none()
    if state is None:
        return None
    created = state.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    expired = _now() - created > _STATE_TTL
    session.delete(state)
    session.commit()
    return None if expired else state


# --- Sessions ---------------------------------------------------------------


def create_session(session: Session, user: User) -> AuthSession:
    ttl = timedelta(hours=get_settings().session_ttl_hours)
    auth_session = AuthSession(
        token=_token(),
        user_id=user.id,
        expires_at=_now() + ttl,
    )
    session.add(auth_session)
    user.last_login_at = _now()
    session.commit()
    return auth_session


def get_user_for_token(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    auth_session = session.execute(
        select(AuthSession).where(AuthSession.token == token)
    ).scalar_one_or_none()
    if auth_session is None:
        return None
    expires = auth_session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < _now():
        session.delete(auth_session)
        session.commit()
        return None
    user = session.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def delete_session(session: Session, token: str | None) -> None:
    if not token:
        return
    auth_session = session.execute(
        select(AuthSession).where(AuthSession.token == token)
    ).scalar_one_or_none()
    if auth_session is not None:
        session.delete(auth_session)
        session.commit()


# --- User provisioning ------------------------------------------------------


def _user_count(session: Session) -> int:
    return int(session.execute(select(func.count(User.id))).scalar_one())


def _owner_exists(session: Session) -> bool:
    return session.execute(select(User.id).where(User.role == ROLE_ADMIN)).first() is not None


def _claim_orphans(session: Session, owner: User) -> None:
    """Assign pre-auth rows (user_id IS NULL) to the Owner on first login."""
    for model in (Mathom, Tag, Collection):
        session.execute(update(model).where(model.user_id.is_(None)).values(user_id=owner.id))


def _extract_claims(claims: dict[str, Any]) -> tuple[str, str, str]:
    subject = str(claims.get("sub", "")).strip()
    email = str(claims.get("email", "")).strip().lower()
    name = str(claims.get("name") or claims.get("preferred_username") or "").strip()
    return subject, email, name


def upsert_user_from_claims(
    session: Session, claims: dict[str, Any], *, auto_create: bool
) -> User | None:
    """Find or create the Mathom user for an Authentik identity.

    Returns ``None`` when the user is unknown and auto-provisioning is disabled.
    The first user ever seen (or the configured owner email) becomes the Owner
    and adopts any pre-existing unowned Mathoms.
    """
    subject, email, name = _extract_claims(claims)
    if not subject:
        return None

    user = session.execute(select(User).where(User.subject == subject)).scalar_one_or_none()
    if user is None and email and claims.get("email_verified") is True:
        # Email linking is allowed only for verified email and unbound accounts.
        user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None and not user.subject:
            user.subject = subject

    if user is not None:
        if email:
            user.email = email
        if name:
            user.name = name
        session.commit()
        return user

    if not auto_create:
        return None

    owner_email = get_settings().auth_owner_email.strip().lower()
    is_owner = not _owner_exists(session) and (
        _user_count(session) == 0 or (owner_email and email == owner_email)
    )
    user = User(
        subject=subject,
        email=email or f"{subject}@authentik.local",
        name=name,
        role=ROLE_ADMIN if is_owner else ROLE_USER,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    if is_owner:
        _claim_orphans(session, user)
        session.commit()
    return user


def revoke_sessions(session: Session, user: User) -> None:
    session.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
    session.commit()


def local_login(session: Session, email: str, password: str) -> User | None:
    from app.services.passwords import verify_password

    user = session.execute(
        select(User).where(User.email == email.strip().lower())
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user
