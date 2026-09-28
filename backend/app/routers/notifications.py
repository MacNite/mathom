"""Per-user notification preferences and Web Push subscriptions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.models import PushSubscription, User
from app.schemas import (
    ChannelResult,
    NotificationSettingsOut,
    NotificationSettingsUpdate,
    NotificationTestOut,
    PushSubscriptionIn,
    PushUnsubscribeIn,
    WebPushKeyOut,
)
from app.services import notifications, webpush

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _user_id(user: User | None) -> int | None:
    return user.id if user is not None else None


def _owner_clause(user: User | None) -> ColumnElement[bool]:
    if user is None:
        return PushSubscription.user_id.is_(None)
    return PushSubscription.user_id == user.id


def _out(db: Session, user: User | None) -> NotificationSettingsOut:
    config = notifications.get_config(db, _user_id(user))
    devices = db.scalar(
        select(func.count()).select_from(PushSubscription).where(_owner_clause(user))
    )
    return NotificationSettingsOut(
        enabled=get_settings().notifications_enabled,
        notify_on_ready=config.notify_on_ready,
        notify_on_error=config.notify_on_error,
        ntfy_url=config.ntfy_url,
        webhook_url=config.webhook_url,
        ntfy_token_set=bool(config.ntfy_token),
        webhook_secret_set=bool(config.webhook_secret),
        web_push_devices=int(devices or 0),
        public_base_url_set=bool(notifications.public_base_url(db)),
    )


@router.get("/settings", response_model=NotificationSettingsOut)
def get_notification_settings(
    db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> NotificationSettingsOut:
    return _out(db, user)


@router.put("/settings", response_model=NotificationSettingsOut)
def put_notification_settings(
    payload: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> NotificationSettingsOut:
    try:
        notifications.update_config(db, _user_id(user), payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(db, user)


@router.post("/test", response_model=NotificationTestOut)
def send_test_notification(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
    accept_language: str | None = Header(default=None),
) -> NotificationTestOut:
    if not get_settings().notifications_enabled:
        raise HTTPException(status_code=409, detail="Notifications are turned off on this server.")
    notice = notifications.build_test_notice(db, accept_language)
    outcomes = notifications.deliver(db, _user_id(user), notice)
    return NotificationTestOut(
        results=[ChannelResult(channel=o.channel, ok=o.ok, detail=o.detail) for o in outcomes]
    )


@router.get("/webpush/key", response_model=WebPushKeyOut)
def get_web_push_key(
    db: Session = Depends(get_db), _user: User | None = Depends(current_user)
) -> WebPushKeyOut:
    return WebPushKeyOut(public_key=webpush.get_vapid_public_key(db))


@router.post("/webpush/subscriptions", status_code=204)
def add_push_subscription(
    payload: PushSubscriptionIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
    user_agent: str | None = Header(default=None),
) -> Response:
    if not get_settings().notifications_enabled:
        raise HTTPException(status_code=409, detail="Notifications are turned off on this server.")
    if not webpush.endpoint_allowed(payload.endpoint):
        raise HTTPException(status_code=422, detail="This browser's push service isn't allowed.")
    try:
        public = webpush.b64url_decode(payload.keys.p256dh)
        secret = webpush.b64url_decode(payload.keys.auth)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid subscription keys.") from exc
    if len(public) != 65 or public[0] != 4 or len(secret) != 16:
        raise HTTPException(status_code=422, detail="Invalid subscription keys.")

    existing = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )
    if existing is None:
        existing = PushSubscription(endpoint=payload.endpoint)
        db.add(existing)
    # A device belongs to whoever subscribed it last (e.g. a shared tablet).
    existing.user_id = _user_id(user)
    existing.p256dh = payload.keys.p256dh
    existing.auth = payload.keys.auth
    existing.user_agent = (user_agent or "")[:300]
    db.commit()
    return Response(status_code=204)


@router.post("/webpush/unsubscribe", status_code=204)
def remove_push_subscription(
    payload: PushUnsubscribeIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    existing = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint, _owner_clause(user)
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return Response(status_code=204)
