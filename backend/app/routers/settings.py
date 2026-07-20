"""Owner-configurable Authentik connection settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import AuthentikSettingsOut, AuthentikSettingsUpdate
from app.services import oidc
from app.services.settings_store import (
    AuthentikConfig,
    get_authentik_config,
    update_authentik_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(config: AuthentikConfig) -> AuthentikSettingsOut:
    return AuthentikSettingsOut(
        issuer=config.issuer,
        client_id=config.client_id,
        scopes=config.scopes,
        public_base_url=config.public_base_url,
        auto_create_users=config.auto_create_users,
        verify_ssl=config.verify_ssl,
        configured=config.configured,
        client_secret_set=bool(config.client_secret),
    )


@router.get("/authentik", response_model=AuthentikSettingsOut)
def get_authentik(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> AuthentikSettingsOut:
    return _to_out(get_authentik_config(db))


@router.put("/authentik", response_model=AuthentikSettingsOut)
def put_authentik(
    payload: AuthentikSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AuthentikSettingsOut:
    config = update_authentik_config(db, payload.model_dump(exclude_unset=True))
    # Discovery may now point at a different issuer; drop the cached document.
    oidc.clear_discovery_cache()
    return _to_out(config)
