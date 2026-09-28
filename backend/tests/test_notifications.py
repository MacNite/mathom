"""Ready/error notifications: preferences API, channels, Web Push crypto.

No network: every outbound ``httpx.post`` is captured by a fake.
"""

import io
import json
from dataclasses import dataclass, field

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.services import notifications, webpush

# RFC 8291 Appendix A example.
RFC = {
    "as_priv": "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw",
    "as_pub": (
        "BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
    ),
    "ua_pub": (
        "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
    ),
    "salt": "DGv6ra1nlYgDCS1FRnbzlw",
    "auth": "BTBZMqHH6r4Tts7J_aSIgg",
    "ciphertext": "8pfeW0KbunFT06SuDKoJH9Ql87S1QUrdirN6GcG7sFz1y1sqLgVi1VhjVkHsUoEsbI_0LpXMuGvnzQ",
}
FCM_ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


@dataclass
class Recorder:
    calls: list[dict] = field(default_factory=list)
    status: int = 201

    def __call__(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return httpx.Response(self.status, request=httpx.Request("POST", url))

    def to(self, prefix: str) -> list[dict]:
        return [c for c in self.calls if c["url"].startswith(prefix)]


@pytest.fixture()
def outbound(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(httpx, "post", recorder)
    # Deliver on the calling thread so tests can assert right away.
    monkeypatch.setattr(notifications, "_submit", lambda fn, *args: fn(*args))
    return recorder


def _ua_keys() -> tuple[ec.EllipticCurvePrivateKey, dict[str, str]]:
    key = ec.generate_private_key(ec.SECP256R1())
    return key, {
        "p256dh": webpush.b64url_encode(webpush._public_bytes(key.public_key())),
        "auth": webpush.b64url_encode(b"0123456789abcdef"),
    }


# --- crypto ---------------------------------------------------------------------------


def test_encrypt_matches_rfc8291_example() -> None:
    server_key = webpush._private_from_raw(webpush.b64url_decode(RFC["as_priv"]))
    assert webpush.b64url_encode(webpush._public_bytes(server_key.public_key())) == RFC["as_pub"]

    body = webpush.encrypt(
        b"When I grow up, I want to be a watermelon",
        webpush.b64url_decode(RFC["ua_pub"]),
        webpush.b64url_decode(RFC["auth"]),
        salt=webpush.b64url_decode(RFC["salt"]),
        server_key=server_key,
    )

    assert body[:16] == webpush.b64url_decode(RFC["salt"])
    assert body[16:21] == b"\x00\x00\x10\x00\x41"  # rs=4096, idlen=65
    assert webpush.b64url_encode(body[21:86]) == RFC["as_pub"]
    assert webpush.b64url_encode(body[86:]) == RFC["ciphertext"]


def test_vapid_header_is_a_verifiable_es256_jwt() -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    key = ec.generate_private_key(ec.SECP256R1())
    header = webpush.vapid_authorization(key, FCM_ENDPOINT, "mailto:a@b.c", now=1000)
    token = header.split("t=")[1].split(",")[0]
    head, claims, signature = token.split(".")
    decoded = json.loads(webpush.b64url_decode(claims))
    assert decoded == {
        "aud": "https://fcm.googleapis.com",
        "exp": 1000 + 43200,
        "sub": "mailto:a@b.c",
    }

    raw = webpush.b64url_decode(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    key.public_key().verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))


def test_endpoint_allowlist() -> None:
    assert webpush.endpoint_allowed(FCM_ENDPOINT)
    assert webpush.endpoint_allowed("https://web.push.apple.com/QGx")
    assert not webpush.endpoint_allowed("http://fcm.googleapis.com/fcm/send/x")
    assert not webpush.endpoint_allowed("https://evil.example.com/fcm.googleapis.com")
    assert not webpush.endpoint_allowed("https://fcm.googleapis.com.evil.example/x")
    assert not webpush.endpoint_allowed("https://ollama:11434/api/pull")


# --- URL validation -------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "ftp://ntfy.example.com/mathom",
        "https://user:pw@ntfy.example.com/mathom",
        "http://localhost:8000/mathom",
        "http://127.0.0.1/mathom",
        "http://[::1]/mathom",
        "http://169.254.169.254/latest",
        "http://ollama:11434/api",
        "https://ntfy.example.com/",
    ],
)
def test_rejects_unusable_channel_urls(client: TestClient, url: str) -> None:
    response = client.put("/api/notifications/settings", json={"ntfy_url": url})
    assert response.status_code == 422, response.text


def test_lan_hosts_are_allowed() -> None:
    assert notifications.validate_target_url("http://192.168.1.20:8090/mathom", ntfy=True)
    assert notifications.validate_target_url("https://ntfy.home.arpa/mathom", ntfy=True)


# --- settings API -----------------------------------------------------------------------


def test_settings_roundtrip_hides_secrets(client: TestClient) -> None:
    initial = client.get("/api/notifications/settings").json()
    assert initial["enabled"] is True
    assert initial["notify_on_ready"] is True
    assert initial["ntfy_url"] == ""

    saved = client.put(
        "/api/notifications/settings",
        json={
            "ntfy_url": "https://ntfy.example.com/mathom",
            "ntfy_token": "tk_secret",
            "webhook_url": "https://hooks.example.com/in",
            "webhook_secret": "shh",
            "notify_on_error": False,
        },
    ).json()
    assert saved["ntfy_url"] == "https://ntfy.example.com/mathom"
    assert saved["ntfy_token_set"] is True
    assert saved["webhook_secret_set"] is True
    assert saved["notify_on_error"] is False
    assert "tk_secret" not in json.dumps(saved)

    # A blank secret keeps the stored one; clearing the URL forgets it.
    kept = client.put("/api/notifications/settings", json={"ntfy_token": ""}).json()
    assert kept["ntfy_token_set"] is True
    cleared = client.put("/api/notifications/settings", json={"ntfy_url": ""}).json()
    assert cleared["ntfy_url"] == ""
    assert cleared["ntfy_token_set"] is False


def test_test_endpoint_reports_each_channel(client: TestClient, outbound: Recorder) -> None:
    client.put(
        "/api/notifications/settings",
        json={"ntfy_url": "https://ntfy.example.com/mathom", "ntfy_token": "tk"},
    )
    response = client.post("/api/notifications/test", headers={"Accept-Language": "de-DE"})
    assert response.status_code == 200, response.text
    assert response.json()["results"] == [{"channel": "ntfy", "ok": True, "detail": "sent"}]

    [call] = outbound.to("https://ntfy.example.com")
    assert call["url"] == "https://ntfy.example.com/"
    assert call["json"]["topic"] == "mathom"
    assert call["json"]["title"] == "Mathom-Benachrichtigungen funktionieren"
    assert call["headers"]["Authorization"] == "Bearer tk"


def test_failed_channel_is_reported_not_raised(client: TestClient, outbound: Recorder) -> None:
    outbound.status = 500
    client.put("/api/notifications/settings", json={"webhook_url": "https://hooks.example.com/x"})
    results = client.post("/api/notifications/test").json()["results"]
    assert results == [{"channel": "webhook", "ok": False, "detail": "answered 500"}]


# --- Web Push subscriptions -------------------------------------------------------------


def test_subscribe_and_unsubscribe(client: TestClient) -> None:
    key = client.get("/api/notifications/webpush/key").json()["public_key"]
    assert len(webpush.b64url_decode(key)) == 65
    # Stable across calls: generated once and stored.
    assert client.get("/api/notifications/webpush/key").json()["public_key"] == key

    _, keys = _ua_keys()
    sub = {"endpoint": FCM_ENDPOINT, "keys": keys}
    assert client.post("/api/notifications/webpush/subscriptions", json=sub).status_code == 204
    assert client.post("/api/notifications/webpush/subscriptions", json=sub).status_code == 204
    assert client.get("/api/notifications/settings").json()["web_push_devices"] == 1

    response = client.post(
        "/api/notifications/webpush/unsubscribe", json={"endpoint": FCM_ENDPOINT}
    )
    assert response.status_code == 204
    assert client.get("/api/notifications/settings").json()["web_push_devices"] == 0


def test_subscription_rejects_foreign_endpoint_and_bad_keys(client: TestClient) -> None:
    _, keys = _ua_keys()
    foreign = {"endpoint": "https://internal.example/hook", "keys": keys}
    assert client.post("/api/notifications/webpush/subscriptions", json=foreign).status_code == 422
    bad = {"endpoint": FCM_ENDPOINT, "keys": {"p256dh": "A" * 40, "auth": keys["auth"]}}
    assert client.post("/api/notifications/webpush/subscriptions", json=bad).status_code == 422


# --- pipeline integration -------------------------------------------------------------


def _upload(client: TestClient) -> int:
    response = client.post(
        "/api/mathoms",
        files={"file": ("PTT-20260722-WA0004.opus", io.BytesIO(b"fake"), "audio/ogg")},
        data={"title": "Garden plans"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_ready_mathom_notifies_every_channel(
    client: TestClient, outbound: Recorder, wait_for_status, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MATHOM_PUBLIC_BASE_URL", "https://mathom.example.com")
    from app.config import get_settings

    get_settings.cache_clear()
    ua_key, keys = _ua_keys()
    client.post(
        "/api/notifications/webpush/subscriptions", json={"endpoint": FCM_ENDPOINT, "keys": keys}
    )
    client.put(
        "/api/notifications/settings",
        json={
            "ntfy_url": "https://ntfy.example.com/mathom",
            "webhook_url": "https://hooks.example.com/in",
            "webhook_secret": "shh",
        },
    )

    mathom_id = _upload(client)
    assert wait_for_status(client, mathom_id)["status"] == "ready"

    [ntfy] = outbound.to("https://ntfy.example.com")
    assert ntfy["json"]["title"] == "“Garden plans” is ready"
    assert ntfy["json"]["message"] == "Mocked AI reply."
    assert ntfy["json"]["click"] == f"https://mathom.example.com/mathoms/{mathom_id}"

    [hook] = outbound.to("https://hooks.example.com")
    payload = json.loads(hook["content"])
    assert payload["event"] == "mathom.ready"
    assert payload["mathom_id"] == mathom_id
    assert hook["headers"]["X-Mathom-Signature"] == notifications.webhook_signature(
        "shh", hook["content"]
    )

    [push] = outbound.to(FCM_ENDPOINT)
    assert push["headers"]["Content-Encoding"] == "aes128gcm"
    assert push["headers"]["Authorization"].startswith("vapid t=")
    decrypted = _decrypt(push["content"], ua_key, webpush.b64url_decode(keys["auth"]))
    assert json.loads(decrypted) == {
        "title": "“Garden plans” is ready",
        "body": "Mocked AI reply.",
        "url": f"/mathoms/{mathom_id}",
        "tag": f"mathom-{mathom_id}",
    }


def test_ready_notification_respects_opt_out(
    client: TestClient, outbound: Recorder, wait_for_status
) -> None:
    client.put(
        "/api/notifications/settings",
        json={"ntfy_url": "https://ntfy.example.com/mathom", "notify_on_ready": False},
    )
    mathom_id = _upload(client)
    assert wait_for_status(client, mathom_id)["status"] == "ready"
    assert outbound.to("https://ntfy.example.com") == []


def test_expired_push_subscription_is_removed(
    client: TestClient, outbound: Recorder, wait_for_status
) -> None:
    outbound.status = 410
    _, keys = _ua_keys()
    client.post(
        "/api/notifications/webpush/subscriptions", json={"endpoint": FCM_ENDPOINT, "keys": keys}
    )
    mathom_id = _upload(client)
    assert wait_for_status(client, mathom_id)["status"] == "ready"
    assert client.get("/api/notifications/settings").json()["web_push_devices"] == 0


def test_kill_switch_disables_everything(
    client: TestClient, outbound: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put("/api/notifications/settings", json={"ntfy_url": "https://ntfy.example.com/m"})
    monkeypatch.setenv("MATHOM_NOTIFICATIONS_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    assert client.get("/api/notifications/settings").json()["enabled"] is False
    assert client.post("/api/notifications/test").status_code == 409
    notifications.notify_mathom(1, notifications.EVENT_READY)
    assert outbound.calls == []


def test_notice_error_uses_error_message(client: TestClient) -> None:
    from app.db import get_session_factory
    from app.models import Mathom

    with get_session_factory()() as session:
        mathom = Mathom(title="Call", status="error", error_message="Ollama is **not** reachable.")
        session.add(mathom)
        session.commit()
        notice = notifications.build_notice(session, mathom, notifications.EVENT_ERROR)
    assert notice.title == "“Call” couldn't be finished"
    assert notice.body == "Ollama is not reachable."
    assert notice.url == ""  # no public base URL configured


def _decrypt(body: bytes, ua_key: ec.EllipticCurvePrivateKey, auth: bytes) -> bytes:
    """Receiver side of RFC 8291, so the test checks what a browser would see."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt, as_public, ciphertext = body[:16], body[21:86], body[86:]
    ua_public = webpush._public_bytes(ua_key.public_key())
    shared = ua_key.exchange(
        ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    )
    ikm = webpush._hkdf(auth, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = webpush._hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = webpush._hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plaintext = AESGCM(cek).decrypt(nonce, ciphertext, None)
    assert plaintext.endswith(b"\x02")
    return plaintext[:-1]
