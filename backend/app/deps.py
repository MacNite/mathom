"""FastAPI dependencies for authentication, RBAC, and per-user scoping.

The single most important rule: when ``auth_enabled`` is false these
dependencies return ``None`` and impose no scoping, so the app behaves exactly
as the original single-user archive.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import ColumnElement, true
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ROLE_ADMIN, User
from app.services import api_tokens, auth
from app.services.settings_store import local_login_enabled


def _cookie_token(request: Request) -> str | None:
    return request.cookies.get(get_settings().session_cookie_name)


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """The principal for data endpoints.

    - auth disabled → ``None`` (no login, no scoping).
    - auth enabled  → the signed-in user, or 401 if the session is missing.
    """
    if not get_settings().auth_enabled:
        return None
    user = auth.get_user_for_token(db, _cookie_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """The signed-in user if there is one, else ``None`` — never raises.

    Used by public endpoints (like auth status) that must respond whether or
    not the caller is logged in.
    """
    if not get_settings().auth_enabled:
        return None
    return auth.get_user_for_token(db, _cookie_token(request))


def authenticated_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Require a real signed-in user (admin/settings endpoints).

    Always 401s when auth is disabled — there is no user to act as.
    """
    if not get_settings().auth_enabled:
        raise HTTPException(status_code=403, detail="User management is disabled")
    user = auth.get_user_for_token(db, _cookie_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(user: User = Depends(authenticated_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


require_admin = require_roles(ROLE_ADMIN)
# Compatibility alias: settings are now administered by admins.
require_owner = require_admin


def require_admin_when_auth_enabled(
    user: User | None = Depends(current_user),
) -> User | None:
    """Allow shared configuration edits only to admins in multi-user mode.

    Prompt templates are global rather than user-owned: changing one affects
    every user's future summaries.  In the original auth-disabled, single-user
    mode there is no principal to authorize, so retain the existing editable
    behavior.  Once authentication is enabled, treat templates as shared
    configuration and require an administrator.
    """
    if user is not None and user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


def owned_filter(model: Any, user: User | None) -> ColumnElement[bool]:
    """WHERE clause that restricts a query to the current user's rows.

    ``model`` is a mapped class with a ``user_id`` column (Mathom, Tag,
    Collection). With no user (auth disabled) this is a no-op ``TRUE`` so every
    row matches.
    """
    if user is None:
        return true()
    return model.user_id == user.id


def owns(obj: object, user: User | None) -> bool:
    if user is None:
        return True
    return getattr(obj, "user_id", None) == user.id


def ingest_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """The principal behind an ``Authorization: Bearer mth_…`` API token.

    Always required, even with auth disabled, so automation endpoints are
    never open. Returns ``None`` in single-user mode and the token's (active)
    owner otherwise; anything else is a 401.
    """
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    challenge = {"WWW-Authenticate": "Bearer"}
    if scheme.lower() != "bearer" or not value.strip():
        raise HTTPException(status_code=401, detail="An API token is required", headers=challenge)
    token = api_tokens.authenticate(db, value.strip())
    if token is None:
        raise HTTPException(
            status_code=401, detail="Invalid or expired API token", headers=challenge
        )
    if not get_settings().auth_enabled:
        return None
    user = db.get(User, token.user_id) if token.user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="Invalid or expired API token", headers=challenge
        )
    return user


def require_local_login(db: Session = Depends(get_db)) -> None:
    """Refuse password-based endpoints while password sign-in is turned off."""
    if get_settings().auth_enabled and not local_login_enabled(db):
        raise HTTPException(403, "Password sign-in is turned off; continue with Authentik")
