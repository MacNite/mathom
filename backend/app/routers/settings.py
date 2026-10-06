"""Owner-configurable Authentik connection settings."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import (
    AuthentikSettingsOut,
    AuthentikSettingsUpdate,
    SmtpSettingsOut,
    SmtpSettingsUpdate,
)
from app.services import oidc
from app.services.settings_store import (
    AuthentikConfig,
    SmtpConfig,
    get_authentik_config,
    get_smtp_config,
    local_login_enabled,
    local_login_override,
    update_authentik_config,
    update_smtp_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(config: AuthentikConfig, db: Session) -> AuthentikSettingsOut:
    return AuthentikSettingsOut(
        issuer=config.issuer,
        client_id=config.client_id,
        scopes=config.scopes,
        public_base_url=config.public_base_url,
        auto_create_users=config.auto_create_users,
        verify_ssl=config.verify_ssl,
        configured=config.configured,
        client_secret_set=bool(config.client_secret),
        local_login_enabled=local_login_enabled(db),
        local_login_locked=local_login_override() is not None,
    )


def _apply(config: AuthentikConfig, updates: dict[str, object]) -> AuthentikConfig:
    """The config as it would be after ``updates`` (mirrors update_authentik_config)."""
    values: dict[str, Any] = {}
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if key == "client_secret" and not value:
                continue
        values[key] = value
    return replace(config, **values)


def _guard_local_login(
    db: Session, admin: User, current: AuthentikConfig, updates: dict[str, object]
) -> None:
    """Refuse changes that could leave nobody able to sign in."""
    override = local_login_override()
    requested = updates.get("local_login_enabled")
    if override is not None and requested is not None and requested != override:
        raise HTTPException(409, "Password sign-in is set by MATHOM_LOCAL_LOGIN_ENABLED")
    after = _apply(current, updates)
    enabled_before = local_login_enabled(db)
    enabled_after = override if override is not None else after.local_login_enabled
    if enabled_after:
        return
    if not after.configured:
        raise HTTPException(
            409, "Authentik must stay configured while password sign-in is turned off"
        )
    if enabled_before and not admin.subject:
        raise HTTPException(
            409,
            "Sign in with Authentik once before turning off password sign-in, "
            "so your account cannot be locked out",
        )


@router.get("/authentik", response_model=AuthentikSettingsOut)
def get_authentik(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> AuthentikSettingsOut:
    return _to_out(get_authentik_config(db), db)


@router.put("/authentik", response_model=AuthentikSettingsOut)
def put_authentik(
    payload: AuthentikSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AuthentikSettingsOut:
    updates = payload.model_dump(exclude_unset=True)
    _guard_local_login(db, admin, get_authentik_config(db), updates)
    config = update_authentik_config(db, updates)
    # Discovery may now point at a different issuer; drop the cached document.
    oidc.clear_discovery_cache()
    return _to_out(config, db)


def _smtp_to_out(config: SmtpConfig) -> SmtpSettingsOut:
    return SmtpSettingsOut(
        host=config.host,
        port=config.port,
        username=config.username,
        from_email=config.from_email,
        from_name=config.from_name,
        public_base_url=config.public_base_url,
        use_tls=config.use_tls,
        invite_expiry_hours=config.invite_expiry_hours,
        configured=config.configured,
        password_set=bool(config.password),
    )


@router.get("/smtp", response_model=SmtpSettingsOut)
def get_smtp(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> SmtpSettingsOut:
    return _smtp_to_out(get_smtp_config(db))


@router.put("/smtp", response_model=SmtpSettingsOut)
def put_smtp(
    payload: SmtpSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> SmtpSettingsOut:
    return _smtp_to_out(update_smtp_config(db, payload.model_dump(exclude_unset=True)))
