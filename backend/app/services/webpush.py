"""Web Push delivery (RFC 8030) with message encryption (RFC 8291) and VAPID
(RFC 8292), implemented on ``cryptography`` + ``httpx``.

The payload is end-to-end encrypted for the subscribing browser: the push
service that relays it (FCM, Mozilla autopush, Apple) sees only ciphertext and
the endpoint. The server's VAPID key pair is generated once and kept in the
``app_settings`` table.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import struct
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSetting

logger = logging.getLogger("mathom.webpush")

_PRIVATE_KEY_SETTING = "webpush.vapid_private_key"
_RECORD_SIZE = 4096
# Push services accept at least 4096 bytes of encrypted body; the fixed header
# (86 bytes), the padding delimiter and the GCM tag leave room for this much.
MAX_PLAINTEXT_BYTES = 3800
_key_lock = threading.Lock()


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    value = value.strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def _private_from_raw(raw: bytes) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


# --- VAPID key pair ----------------------------------------------------------


def get_vapid_private_key(session: Session) -> ec.EllipticCurvePrivateKey:
    """Return the server's VAPID key, generating and storing it on first use."""
    with _key_lock:
        stored = session.get(AppSetting, _PRIVATE_KEY_SETTING)
        if stored is not None and stored.value:
            return _private_from_raw(b64url_decode(stored.value))
        key = ec.generate_private_key(ec.SECP256R1())
        raw = key.private_numbers().private_value.to_bytes(32, "big")
        session.add(AppSetting(key=_PRIVATE_KEY_SETTING, value=b64url_encode(raw)))
        session.commit()
        return key


def get_vapid_public_key(session: Session) -> str:
    """The application server key browsers pass to ``pushManager.subscribe``."""
    return b64url_encode(_public_bytes(get_vapid_private_key(session).public_key()))


def vapid_authorization(
    key: ec.EllipticCurvePrivateKey, endpoint: str, subject: str, *, now: float | None = None
) -> str:
    """Build the ``Authorization: vapid t=…, k=…`` header for one endpoint."""
    parts = urlsplit(endpoint)
    claims = {
        "aud": f"{parts.scheme}://{parts.netloc}",
        "exp": int((now if now is not None else time.time()) + 12 * 3600),
        "sub": subject,
    }
    header = b64url_encode(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    body = b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode("ascii")
    r, s = decode_dss_signature(key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
    signature = b64url_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    public = b64url_encode(_public_bytes(key.public_key()))
    return f"vapid t={header}.{body}.{signature}, k={public}"


# --- RFC 8291 payload encryption ----------------------------------------------


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(
    plaintext: bytes,
    ua_public: bytes,
    auth_secret: bytes,
    *,
    salt: bytes | None = None,
    server_key: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """Encrypt ``plaintext`` for one subscription as a single aes128gcm record.

    ``salt`` and ``server_key`` are only injected by tests (to reproduce the
    RFC 8291 example); in production both are fresh for every message.
    """
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise ValueError("push payload too large")
    salt = salt if salt is not None else os.urandom(16)
    server_key = server_key if server_key is not None else ec.generate_private_key(ec.SECP256R1())
    as_public = _public_bytes(server_key.public_key())
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    ecdh_secret = server_key.exchange(ec.ECDH(), ua_key)

    key_info = b"WebPush: info\x00" + ua_public + as_public
    ikm = _hkdf(auth_secret, ecdh_secret, key_info, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    # 0x02 marks the last (and only) record; no extra padding.
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + struct.pack("!IB", _RECORD_SIZE, len(as_public)) + as_public
    return header + ciphertext


# --- Delivery ------------------------------------------------------------------


@dataclass(frozen=True)
class Subscription:
    endpoint: str
    p256dh: str
    auth: str


class SubscriptionGoneError(Exception):
    """The push service says this subscription no longer exists (404/410)."""


def endpoint_allowed(endpoint: str) -> bool:
    """Only deliver to HTTPS endpoints on the configured push-service hosts.

    Browsers hand the server whatever endpoint the push service issued; the
    allowlist keeps a crafted subscription from turning Mathom into a relay
    that POSTs to arbitrary (for example internal) addresses.
    """
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    for allowed in get_settings().web_push_allowed_host_list:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def send(
    key: ec.EllipticCurvePrivateKey,
    subscription: Subscription,
    payload: dict[str, object],
    *,
    subject: str,
    topic: str | None = None,
) -> None:
    """Deliver one encrypted notification. Raises ``SubscriptionGoneError`` when the
    push service reports the subscription expired, ``RuntimeError`` otherwise."""
    if not endpoint_allowed(subscription.endpoint):
        raise RuntimeError("push endpoint is not on the allowed push-service list")
    body = encrypt(
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        b64url_decode(subscription.p256dh),
        b64url_decode(subscription.auth),
    )
    headers = {
        "Authorization": vapid_authorization(key, subscription.endpoint, subject),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(24 * 3600),
        "Urgency": "normal",
    }
    if topic:
        headers["Topic"] = topic
    response = httpx.post(
        subscription.endpoint,
        content=body,
        headers=headers,
        timeout=get_settings().notify_timeout_seconds,
    )
    if response.status_code in (404, 410):
        raise SubscriptionGoneError(subscription.endpoint)
    if response.status_code >= 400:
        raise RuntimeError(f"push service answered {response.status_code}")
