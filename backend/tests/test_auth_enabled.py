"""End-to-end auth flow with Authentik OIDC mocked (see conftest.auth_harness).

``auth_harness`` is an ``AuthHarness`` (defined in conftest) provided by fixture;
it is intentionally left unannotated so the module needs no cross-package import
(pytest is invoked as bare ``pytest`` in CI, where ``tests`` is not importable).
"""

import io

from fastapi.testclient import TestClient

OWNER = {"sub": "owner-sub", "email": "owner@example.com", "name": "Archive Owner"}
ALICE = {"sub": "alice-sub", "email": "alice@example.com", "name": "Alice"}
BOB = {"sub": "bob-sub", "email": "bob@example.com", "name": "Bob"}


def _upload(client: TestClient, title: str) -> int:
    response = client.post(
        "/api/mathoms",
        files={"file": ("r.mp3", io.BytesIO(b"bytes"), "audio/mpeg")},
        data={"title": title},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_status_and_unauthenticated_access(auth_harness) -> None:
    client = auth_harness.client()
    status = client.get("/api/auth/status").json()
    assert status["auth_enabled"] is True
    assert status["configured"] is True
    assert status["authenticated"] is False
    # Data endpoints require a session now.
    assert client.get("/api/mathoms").status_code == 401


def test_first_user_becomes_admin(auth_harness) -> None:
    client = auth_harness.client()
    auth_harness.login(client, OWNER)
    me = client.get("/api/auth/status").json()
    assert me["authenticated"] is True
    assert me["user"]["role"] == "admin"
    assert me["user"]["email"] == "owner@example.com"


def test_second_user_is_isolated(auth_harness) -> None:
    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    owner_mathom = _upload(owner, "Owner's memory")

    alice = auth_harness.client()
    auth_harness.login(alice, ALICE)
    assert alice.get("/api/auth/status").json()["user"]["role"] == "user"

    # Alice sees none of the owner's Mathoms and cannot open one by id.
    assert alice.get("/api/mathoms").json() == []
    assert alice.get(f"/api/mathoms/{owner_mathom}").status_code == 404

    alice_mathom = _upload(alice, "Alice's memory")
    assert {m["id"] for m in alice.get("/api/mathoms").json()} == {alice_mathom}
    # Owner likewise cannot see Alice's Mathom.
    assert owner.get(f"/api/mathoms/{alice_mathom}").status_code == 404


def test_rbac_user_management(auth_harness) -> None:
    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    alice = auth_harness.client()
    auth_harness.login(alice, ALICE)

    # A plain user cannot reach admin endpoints.
    assert alice.get("/api/users").status_code == 403
    assert alice.get("/api/settings/authentik").status_code == 403

    users = owner.get("/api/users").json()
    assert owner.get("/api/users").status_code == 200
    alice_id = next(u["id"] for u in users if u["email"] == ALICE["email"])

    # Admin promotes Alice to admin; admins can manage users.
    assert owner.patch(f"/api/users/{alice_id}", json={"role": "admin"}).status_code == 200
    assert alice.get("/api/users").status_code == 200
    bob = auth_harness.client()
    auth_harness.login(bob, BOB)
    bob_id = next(u["id"] for u in owner.get("/api/users").json() if u["email"] == BOB["email"])
    assert alice.patch(f"/api/users/{bob_id}", json={"role": "admin"}).status_code == 200
    # But an admin may deactivate a plain user.
    assert alice.patch(f"/api/users/{bob_id}", json={"is_active": False}).status_code == 200
    # Deactivated Bob can no longer use his session.
    assert bob.get("/api/mathoms").status_code == 401


def test_owner_cannot_be_demoted_into_lockout(auth_harness) -> None:
    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    me = owner.get("/api/auth/status").json()["user"]
    resp = owner.patch(f"/api/users/{me['id']}", json={"role": "user"})
    assert resp.status_code == 409


def test_logout_ends_the_session(auth_harness) -> None:
    client = auth_harness.client()
    auth_harness.login(client, OWNER)
    assert client.get("/api/mathoms").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/mathoms").status_code == 401


def test_owner_claims_pre_auth_mathoms(auth_harness) -> None:
    # Simulate a database that predates user management: an unowned Mathom.
    from app.db import get_session_factory
    from app.models import Mathom

    with get_session_factory()() as session:
        session.add(Mathom(title="Legacy memory", status="ready", user_id=None))
        session.commit()

    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    titles = {m["title"] for m in owner.get("/api/mathoms").json()}
    assert "Legacy memory" in titles


def test_settings_update_masks_secret(auth_harness) -> None:
    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    current = owner.get("/api/settings/authentik").json()
    assert "client_secret" not in current
    assert current["client_secret_set"] is True

    updated = owner.put(
        "/api/settings/authentik",
        json={"scopes": "openid email", "client_secret": ""},
    ).json()
    assert updated["scopes"] == "openid email"
    # Blank secret leaves the existing one in place.
    assert updated["client_secret_set"] is True
