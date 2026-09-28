"""Tell people when a Mathom has finished (or failed) processing.

Channels, each opt-in per user:

- **Web Push** to every device that enabled notifications in the PWA.
- **ntfy**: a topic URL on a (usually self-hosted) ntfy server.
- **Webhook**: a JSON POST, optionally HMAC-signed, for Home Assistant & co.

Per-user preferences live in ``app_settings`` under ``notify.<scope>.*`` where
the scope is ``local`` in single-user mode and ``u<id>`` otherwise. Delivery
runs on a small thread pool so a slow endpoint never holds up the job queue,
and a failing channel is logged, never raised into the pipeline.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session_factory
from app.models import AppSetting, Mathom, PushSubscription, Summary
from app.services import webpush
from app.services.settings_store import get_authentik_config, get_smtp_config

logger = logging.getLogger("mathom.notifications")

EVENT_READY = "mathom.ready"
EVENT_ERROR = "mathom.error"
EVENT_TEST = "test"

_PREFIX = "notify."
_STR_KEYS = ("ntfy_url", "ntfy_token", "webhook_url", "webhook_secret")
_SECRET_FOR = {"ntfy_url": "ntfy_token", "webhook_url": "webhook_secret"}
_BOOL_KEYS = ("notify_on_ready", "notify_on_error")
_BODY_CHARS = 240

_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "ready": "“{title}” is ready",
        "ready_body": "The transcript and summary are waiting on the shelf.",
        "error": "“{title}” couldn't be finished",
        "error_body": "Something went wrong while processing this recording.",
        "test": "Mathom notifications are working",
        "test_body": "This is a test. Finished recordings will arrive here.",
    },
    "de": {
        "ready": "„{title}“ ist fertig",
        "ready_body": "Transkript und Zusammenfassung liegen bereit.",
        "error": "„{title}“ konnte nicht fertiggestellt werden",
        "error_body": "Beim Verarbeiten dieser Aufnahme ist etwas schiefgegangen.",
        "test": "Mathom-Benachrichtigungen funktionieren",
        "test_body": "Das ist ein Test. Fertige Aufnahmen erscheinen künftig hier.",
    },
    "es": {
        "ready": "«{title}» está listo",
        "ready_body": "La transcripción y el resumen te esperan en la estantería.",
        "error": "No se pudo terminar «{title}»",
        "error_body": "Algo salió mal al procesar esta grabación.",
        "test": "Las notificaciones de Mathom funcionan",
        "test_body": "Esto es una prueba. Las grabaciones terminadas llegarán aquí.",
    },
}


def _text(lang: str | None, key: str) -> str:
    return _TEXT.get((lang or "en")[:2], _TEXT["en"])[key]


# --- Preferences -----------------------------------------------------------------


@dataclass
class NotificationConfig:
    notify_on_ready: bool = True
    notify_on_error: bool = True
    ntfy_url: str = ""
    ntfy_token: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""


def _scope(user_id: int | None) -> str:
    return "local" if user_id is None else f"u{user_id}"


def get_config(session: Session, user_id: int | None) -> NotificationConfig:
    prefix = f"{_PREFIX}{_scope(user_id)}."
    rows = session.execute(
        select(AppSetting.key, AppSetting.value).where(AppSetting.key.like(f"{prefix}%"))
    ).all()
    stored = {key[len(prefix) :]: value for key, value in rows}
    config = NotificationConfig()
    for key in _STR_KEYS:
        if key in stored:
            setattr(config, key, stored[key])
    for key in _BOOL_KEYS:
        if key in stored:
            setattr(config, key, stored[key] == "true")
    return config


def _set(session: Session, user_id: int | None, key: str, value: str) -> None:
    full = f"{_PREFIX}{_scope(user_id)}.{key}"
    setting = session.get(AppSetting, full)
    if setting is None:
        session.add(AppSetting(key=full, value=value))
    else:
        setting.value = value


def update_config(
    session: Session, user_id: int | None, updates: dict[str, object]
) -> NotificationConfig:
    """Persist a partial update. Raises ``ValueError`` for an unusable URL.

    A blank token/secret keeps the stored one; clearing a URL also forgets its
    secret, so a removed channel leaves nothing behind.
    """
    for url_key in ("ntfy_url", "webhook_url"):
        if updates.get(url_key) is not None:
            updates[url_key] = validate_target_url(
                str(updates[url_key]), ntfy=url_key == "ntfy_url"
            )
    for key in _STR_KEYS:
        value = updates.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if key in _SECRET_FOR.values() and text == "":
            continue
        _set(session, user_id, key, text)
        if key in _SECRET_FOR and text == "":
            _set(session, user_id, _SECRET_FOR[key], "")
    for key in _BOOL_KEYS:
        if updates.get(key) is not None:
            _set(session, user_id, key, "true" if updates[key] else "false")
    session.commit()
    return get_config(session, user_id)


def _blocked_host(host: str) -> bool:
    """Hosts a user-supplied URL may not target: this container's loopback
    (the backend itself), link-local metadata ranges, and the Ollama service."""
    host = host.lower().rstrip(".")
    ollama_host = (urlsplit(get_settings().ollama_base_url).hostname or "").lower()
    if host in {"localhost", "ollama", ollama_host} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified or ip.is_link_local or ip.is_multicast


def validate_target_url(raw: str, *, ntfy: bool = False) -> str:
    """Return a cleaned channel URL (``""`` clears it) or raise ``ValueError``."""
    url = raw.strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises on a malformed port
    except ValueError as exc:
        raise ValueError("That doesn't look like a valid address.") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Use a full http:// or https:// address.")
    if parts.username or parts.password:
        raise ValueError("Put credentials in the token or secret field, not in the address.")
    if _blocked_host(parts.hostname):
        raise ValueError("That address points inside Mathom itself and can't be used.")
    if ntfy and not parts.path.strip("/"):
        raise ValueError("Include the topic, e.g. https://ntfy.example.com/mathom.")
    return url


# --- Building a notice ---------------------------------------------------------------


@dataclass(frozen=True)
class Notice:
    event: str
    title: str
    body: str
    mathom_id: int | None = None
    # Always a same-origin path (for Web Push); ``url`` is absolute when a
    # public base URL is known, else empty.
    path: str = "/"
    url: str = ""


@dataclass
class ChannelOutcome:
    channel: str
    ok: bool
    detail: str = ""


@dataclass
class _Targets:
    user_id: int | None
    config: NotificationConfig
    subscriptions: list[PushSubscription] = field(default_factory=list)


def public_base_url(session: Session) -> str:
    return (
        get_authentik_config(session).public_base_url or get_smtp_config(session).public_base_url
    ).rstrip("/")


def _plain_excerpt(markdown: str, limit: int = _BODY_CHARS) -> str:
    text = re.sub(r"[#*_`>|]+", " ", markdown)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_notice(session: Session, mathom: Mathom, event: str) -> Notice:
    lang = mathom.template_language
    title = (mathom.title or "").strip() or "Mathom"
    if event == EVENT_READY:
        latest = session.scalars(
            select(Summary)
            .where(Summary.mathom_id == mathom.id)
            .order_by(Summary.created_at.desc(), Summary.id.desc())
            .limit(1)
        ).first()
        body = _plain_excerpt(latest.content) if latest and latest.content else ""
        heading, body = _text(lang, "ready").format(title=title), body or _text(lang, "ready_body")
    else:
        heading = _text(lang, "error").format(title=title)
        body = _plain_excerpt(mathom.error_message or "") or _text(lang, "error_body")
    path = f"/mathoms/{mathom.id}"
    base = public_base_url(session)
    return Notice(
        event=event,
        title=heading,
        body=body,
        mathom_id=mathom.id,
        path=path,
        url=f"{base}{path}" if base else "",
    )


def build_test_notice(session: Session, lang: str | None) -> Notice:
    base = public_base_url(session)
    return Notice(
        event=EVENT_TEST,
        title=_text(lang, "test"),
        body=_text(lang, "test_body"),
        path="/notifications",
        url=f"{base}/notifications" if base else "",
    )


# --- Channels ------------------------------------------------------------------------


def _describe(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timed out"
    if isinstance(exc, httpx.HTTPError):
        return "couldn't connect"
    return str(exc) or exc.__class__.__name__


def _check(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise RuntimeError(f"answered {response.status_code}")


def send_ntfy(config: NotificationConfig, notice: Notice) -> None:
    # ntfy's JSON publishing API: POST to the server root with the topic inside.
    # JSON (unlike headers) carries any Unicode title safely.
    validate_target_url(config.ntfy_url, ntfy=True)
    base, _, topic = config.ntfy_url.rstrip("/").rpartition("/")
    payload: dict[str, object] = {
        "topic": topic,
        "title": notice.title,
        "message": notice.body,
        "tags": ["warning"] if notice.event == EVENT_ERROR else ["books"],
    }
    if notice.url:
        payload["click"] = notice.url
    headers = {"User-Agent": "Mathom"}
    if config.ntfy_token:
        headers["Authorization"] = f"Bearer {config.ntfy_token}"
    _check(
        httpx.post(
            f"{base}/",
            json=payload,
            headers=headers,
            timeout=get_settings().notify_timeout_seconds,
        )
    )


def webhook_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def send_webhook(config: NotificationConfig, notice: Notice) -> None:
    validate_target_url(config.webhook_url)
    body = json.dumps(
        {
            "event": notice.event,
            "mathom_id": notice.mathom_id,
            "title": notice.title,
            "body": notice.body,
            "path": notice.path,
            "url": notice.url,
            "sent_at": datetime.now(UTC).isoformat(),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mathom",
        "X-Mathom-Event": notice.event,
    }
    if config.webhook_secret:
        headers["X-Mathom-Signature"] = webhook_signature(config.webhook_secret, body)
    _check(
        httpx.post(
            config.webhook_url,
            content=body,
            headers=headers,
            timeout=get_settings().notify_timeout_seconds,
        )
    )


def _web_push_subject(session: Session) -> str:
    contact = get_settings().web_push_contact.strip()
    if contact:
        return contact
    base = public_base_url(session)
    return base if base.startswith("https://") else "mailto:mathom@localhost"


def _send_web_push(session: Session, targets: _Targets, notice: Notice) -> ChannelOutcome:
    key = webpush.get_vapid_private_key(session)
    subject = _web_push_subject(session)
    payload: dict[str, object] = {
        "title": notice.title,
        "body": notice.body,
        "url": notice.path,
        "tag": f"mathom-{notice.mathom_id}" if notice.mathom_id else "mathom-test",
    }
    delivered = 0
    for sub in targets.subscriptions:
        try:
            webpush.send(
                key,
                webpush.Subscription(sub.endpoint, sub.p256dh, sub.auth),
                payload,
                subject=subject,
                topic=f"mathom-{notice.mathom_id}" if notice.mathom_id else None,
            )
        except webpush.SubscriptionGoneError:
            logger.info("Removing expired push subscription %s", sub.id)
            session.delete(sub)
            continue
        except Exception as exc:  # noqa: BLE001 — one bad device must not stop the rest
            logger.warning("Web Push to subscription %s failed: %s", sub.id, _describe(exc))
            continue
        sub.last_success_at = datetime.now(UTC)
        delivered += 1
    session.commit()
    total = len(targets.subscriptions)
    return ChannelOutcome("web_push", delivered > 0, f"{delivered} of {total} devices")


def _load_targets(session: Session, user_id: int | None) -> _Targets:
    owner = (
        PushSubscription.user_id.is_(None)
        if user_id is None
        else PushSubscription.user_id == user_id
    )
    subs = list(session.scalars(select(PushSubscription).where(owner)).all())
    return _Targets(user_id=user_id, config=get_config(session, user_id), subscriptions=subs)


def deliver(session: Session, user_id: int | None, notice: Notice) -> list[ChannelOutcome]:
    """Send ``notice`` on every channel the user configured, synchronously."""
    if not get_settings().notifications_enabled:
        return []
    targets = _load_targets(session, user_id)
    outcomes: list[ChannelOutcome] = []
    senders: list[tuple[str, str, Callable[[NotificationConfig, Notice], None]]] = [
        ("ntfy", targets.config.ntfy_url, send_ntfy),
        ("webhook", targets.config.webhook_url, send_webhook),
    ]
    for channel, configured, sender in senders:
        if not configured:
            continue
        try:
            sender(targets.config, notice)
            outcomes.append(ChannelOutcome(channel, True, "sent"))
        except Exception as exc:  # noqa: BLE001 — report, never raise
            logger.warning("%s notification failed: %s", channel, _describe(exc))
            outcomes.append(ChannelOutcome(channel, False, _describe(exc)))
    if targets.subscriptions:
        outcomes.append(_send_web_push(session, targets, notice))
    return outcomes


# --- Pipeline entry point ------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mathom-notify")


def _submit(fn: Callable[[int, str], None], mathom_id: int, event: str) -> None:
    _executor.submit(fn, mathom_id, event)


def _notify_now(mathom_id: int, event: str) -> None:
    try:
        with get_session_factory()() as session:
            mathom = session.get(Mathom, mathom_id)
            if mathom is None:
                return
            # Single-user mode has one inbox regardless of historic ownership.
            if get_settings().auth_enabled:
                if mathom.user_id is None:
                    return
                user_id: int | None = mathom.user_id
            else:
                user_id = None
            config = get_config(session, user_id)
            if (event == EVENT_READY and not config.notify_on_ready) or (
                event == EVENT_ERROR and not config.notify_on_error
            ):
                return
            deliver(session, user_id, build_notice(session, mathom, event))
    except Exception:  # noqa: BLE001 — notifications are best-effort
        logger.exception("Could not send notifications for mathom %s", mathom_id)


def notify_mathom(mathom_id: int, event: str) -> None:
    """Queue ready/error notifications for a Mathom; returns immediately."""
    if not get_settings().notifications_enabled:
        return
    try:
        _submit(_notify_now, mathom_id, event)
    except RuntimeError:  # executor shut down during interpreter exit
        logger.warning("Notification for mathom %s dropped during shutdown", mathom_id)
