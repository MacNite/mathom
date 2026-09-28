"""API tokens and the token-authenticated ingest endpoints."""

import io
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _token(client: TestClient, name: str = "Tasker", **extra: object) -> str:
    response = client.post("/api/tokens", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token"].startswith("mth_")
    assert body["prefix"] == body["token"][:12]
    return str(body["token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _voice_note(name: str = "PTT-20260722-WA0004.opus", data: bytes = b"voice") -> dict:
    return {"file": (name, io.BytesIO(data), "audio/ogg")}


# --- tokens -------------------------------------------------------------------------


def test_token_lifecycle_never_reveals_the_secret_again(client: TestClient) -> None:
    token = _token(client, expires_in_days=30)
    [listed] = client.get("/api/tokens").json()
    assert listed["name"] == "Tasker"
    assert "token" not in listed
    assert listed["expires_at"] is not None
    assert listed["last_used_at"] is None

    client.post("/api/ingest/audio", files=_voice_note(), headers=_auth(token))
    assert client.get("/api/tokens").json()[0]["last_used_at"] is not None

    assert client.delete(f"/api/tokens/{listed['id']}").status_code == 204
    assert client.get("/api/tokens").json() == []
    revoked = client.post("/api/ingest/audio", files=_voice_note(), headers=_auth(token))
    assert revoked.status_code == 401


def test_ingest_requires_a_valid_token_even_without_login(client: TestClient) -> None:
    assert client.post("/api/ingest/audio", files=_voice_note()).status_code == 401
    bad = client.post("/api/ingest/audio", files=_voice_note(), headers=_auth("mth_nope"))
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_rejected(client: TestClient) -> None:
    from app.db import get_session_factory
    from app.models import ApiToken

    token = _token(client)
    with get_session_factory()() as session:
        row = session.query(ApiToken).one()
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    response = client.post("/api/ingest/audio", files=_voice_note(), headers=_auth(token))
    assert response.status_code == 401


# --- ingest ---------------------------------------------------------------------------


def test_multipart_ingest_with_metadata(client: TestClient, wait_for_status) -> None:
    token = _token(client)
    response = client.post(
        "/api/ingest/audio",
        files=_voice_note(),
        data={
            "speaker": "Rosie",
            "external_source": "whatsapp",
            "external_id": "3EB0C767D26A1D8E5B42",
            "recorded_at": "2026-07-22T09:14:00+02:00",
            "tags": "family, Garden",
            "template_slug": "tldr",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["speaker"] == "Rosie"
    assert body["source_app"] == "WhatsApp"
    assert body["recorded_at"].startswith("2026-07-22T07:14:00")
    assert {"family", "garden"} <= {tag["name"] for tag in body["tags"]}
    # No title given → the pipeline names it (mocked Ollama reply).
    assert wait_for_status(client, body["id"])["title"] != "PTT-20260722-WA0004"


def test_resending_the_same_message_is_idempotent(client: TestClient) -> None:
    token = _token(client)
    data = {"external_source": "whatsapp", "external_id": "msg-1"}
    first = client.post("/api/ingest/audio", files=_voice_note(), data=data, headers=_auth(token))
    again = client.post(
        "/api/ingest/audio",
        files=_voice_note(data=b"re-encoded bytes"),
        data=data,
        headers=_auth(token),
    )
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.headers["x-mathom-duplicate"] == "true"
    assert again.json()["id"] == first.json()["id"]


def test_same_bytes_without_message_id_are_deduplicated(client: TestClient) -> None:
    token = _token(client)
    first = client.post("/api/ingest/audio", files=_voice_note(), headers=_auth(token))
    again = client.post("/api/ingest/audio", files=_voice_note("copy.opus"), headers=_auth(token))
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    # The browser upload keeps its old behaviour: an explicit re-upload is new.
    manual = client.post("/api/mathoms", files=_voice_note())
    assert manual.status_code == 201
    assert manual.json()["id"] != first.json()["id"]


def test_raw_body_ingest(client: TestClient) -> None:
    token = _token(client)
    response = client.post(
        "/api/ingest/audio/raw",
        params={"filename": "../../etc/Recording 2026-07-22 14.03.11.m4a", "title": "Walk"},
        content=b"raw-audio",
        headers={**_auth(token), "Content-Type": "audio/mp4"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Walk"
    assert body["original_filename"] == "Recording 2026-07-22 14.03.11.m4a"


def test_ingest_rejects_unsupported_and_oversized(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    token = _token(client)
    unsupported = client.post(
        "/api/ingest/audio", files=_voice_note("notes.exe"), headers=_auth(token)
    )
    assert unsupported.status_code == 415

    monkeypatch.setenv("MATHOM_MAX_UPLOAD_MB", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    big = client.post(
        "/api/ingest/audio/raw",
        params={"filename": "big.opus"},
        content=b"x" * (1024 * 1024 + 1),
        headers=_auth(token),
    )
    assert big.status_code == 413


def test_tokens_and_ingest_are_scoped_per_user(auth_harness) -> None:  # type: ignore[no-untyped-def]
    alice, bob = auth_harness.client(), auth_harness.client()
    auth_harness.login(alice, {"sub": "a", "email": "alice@example.com", "name": "Alice"})
    auth_harness.login(bob, {"sub": "b", "email": "bob@example.com", "name": "Bob"})

    token = _token(alice)
    assert bob.get("/api/tokens").json() == []
    token_id = alice.get("/api/tokens").json()[0]["id"]
    assert bob.delete(f"/api/tokens/{token_id}").status_code == 404

    # Tokens work without any cookie and file the Mathom under their owner.
    anonymous = auth_harness.client()
    created = anonymous.post("/api/ingest/audio", files=_voice_note(), headers=_auth(token))
    assert created.status_code == 201, created.text
    mathom_id = created.json()["id"]
    assert alice.get(f"/api/mathoms/{mathom_id}").status_code == 200
    assert bob.get(f"/api/mathoms/{mathom_id}").status_code == 404
    # A token never stands in for a session on the regular API.
    assert anonymous.get("/api/mathoms", headers=_auth(token)).status_code == 401


def test_timeline_prefers_recorded_at(client: TestClient) -> None:
    token = _token(client)
    client.post(
        "/api/ingest/audio",
        files=_voice_note(),
        data={"recorded_at": "2024-03-05T10:00:00Z"},
        headers=_auth(token),
    )
    months = {bucket["month"] for bucket in client.get("/api/timeline").json()}
    assert "2024-03" in months
