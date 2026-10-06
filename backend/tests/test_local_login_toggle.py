"""Turning off password sign-in so Authentik is the only way in.

Uses the ``auth_harness`` fixture (see conftest), which mocks Authentik OIDC.
"""

from datetime import timedelta

import pytest

OWNER = {"sub": "owner-sub", "email": "owner@example.com", "name": "Archive Owner"}
ALICE = {"sub": "alice-sub", "email": "alice@example.com", "name": "Alice"}
PASSWORD = "a-secure-password"


def _set_override(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    import app.config as config

    monkeypatch.setenv("MATHOM_LOCAL_LOGIN_ENABLED", value)
    config.get_settings.cache_clear()


def _onboard(client, email: str = "local@example.com") -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/auth/onboarding",
        json={
            "name": "Local Admin",
            "email": email,
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text


def _disable(client):  # type: ignore[no-untyped-def]
    return client.put("/api/settings/authentik", json={"local_login_enabled": False})


def _seed_invitation_token() -> str:
    from app.db import get_session_factory
    from app.models import Invitation, utcnow
    from app.services.invitations import new_token, token_hash

    token = new_token()
    with get_session_factory()() as session:
        session.add(
            Invitation(
                email="invitee@example.com",
                name="Invitee",
                token_hash=token_hash(token),
                expires_at=utcnow() + timedelta(hours=48),
            )
        )
        session.commit()
    return token


def test_password_sign_in_is_on_by_default(auth_harness) -> None:
    client = auth_harness.client()
    assert client.get("/api/auth/status").json()["local_login_available"] is True
    auth_harness.login(client, OWNER)
    settings = client.get("/api/settings/authentik").json()
    assert settings["local_login_enabled"] is True
    assert settings["local_login_locked"] is False


def test_disabling_blocks_password_endpoints(auth_harness) -> None:
    admin = auth_harness.client()
    auth_harness.login(admin, OWNER)
    created = admin.post(
        "/api/users",
        json={"email": "pw@example.com", "password": PASSWORD, "must_change_password": False},
    )
    assert created.status_code == 201, created.text
    token = _seed_invitation_token()

    response = _disable(admin)
    assert response.status_code == 200, response.text
    assert response.json()["local_login_enabled"] is False

    anon = auth_harness.client()
    assert anon.get("/api/auth/status").json()["local_login_available"] is False
    login = anon.post(
        "/api/auth/login/local", json={"email": "pw@example.com", "password": PASSWORD}
    )
    assert login.status_code == 403
    assert (
        anon.post(
            "/api/invitations/accept", json={"token": token, "password": PASSWORD}
        ).status_code
        == 403
    )
    assert (
        admin.post("/api/invitations", json={"email": "new@example.com", "name": "New"}).status_code
        == 403
    )
    assert admin.post("/api/users/me/password", json={"password": PASSWORD}).status_code == 403
    user_id = created.json()["id"]
    assert (
        admin.post(f"/api/users/{user_id}/password", json={"password": PASSWORD}).status_code == 403
    )
    # Authentik sign-in keeps working.
    auth_harness.login(auth_harness.client(), ALICE)


def test_stored_passwords_return_when_re_enabled(auth_harness) -> None:
    admin = auth_harness.client()
    auth_harness.login(admin, OWNER)
    admin.post(
        "/api/users",
        json={"email": "pw@example.com", "password": PASSWORD, "must_change_password": False},
    )
    assert _disable(admin).status_code == 200
    token = _seed_invitation_token()
    enabled = admin.put("/api/settings/authentik", json={"local_login_enabled": True})
    assert enabled.status_code == 200

    anon = auth_harness.client()
    login = anon.post(
        "/api/auth/login/local", json={"email": "pw@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    # The pending invitation was left intact and can be accepted again.
    accepted = anon.post("/api/invitations/accept", json={"token": token, "password": PASSWORD})
    assert accepted.status_code == 200, accepted.text


def test_admins_can_pre_create_passwordless_users(auth_harness) -> None:
    admin = auth_harness.client()
    auth_harness.login(admin, OWNER)
    assert _disable(admin).status_code == 200

    response = admin.post("/api/users", json={"email": "sso@example.com", "name": "SSO"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["has_local_password"] is False
    assert body["must_change_password"] is False
    with_password = admin.post("/api/users", json={"email": "pw@example.com", "password": PASSWORD})
    assert with_password.status_code == 403


def test_cannot_disable_before_linking_own_account(auth_harness) -> None:
    client = auth_harness.client()
    _onboard(client)
    response = _disable(client)
    assert response.status_code == 409
    assert "Sign in with Authentik" in response.json()["detail"]
    assert client.get("/api/auth/status").json()["local_login_available"] is True


def test_cannot_disable_without_authentik(auth_harness) -> None:
    admin = auth_harness.client()
    auth_harness.login(admin, OWNER)
    response = admin.put(
        "/api/settings/authentik", json={"local_login_enabled": False, "issuer": ""}
    )
    assert response.status_code == 409
    # Nor can Authentik be unconfigured while password sign-in is off.
    assert _disable(admin).status_code == 200
    assert admin.put("/api/settings/authentik", json={"client_id": " "}).status_code == 409


def test_env_true_is_a_break_glass_override(auth_harness, monkeypatch) -> None:
    admin = auth_harness.client()
    auth_harness.login(admin, OWNER)
    admin.post(
        "/api/users",
        json={"email": "pw@example.com", "password": PASSWORD, "must_change_password": False},
    )
    assert _disable(admin).status_code == 200

    _set_override(monkeypatch, "true")
    anon = auth_harness.client()
    assert anon.get("/api/auth/status").json()["local_login_available"] is True
    login = anon.post(
        "/api/auth/login/local", json={"email": "pw@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    settings = admin.get("/api/settings/authentik").json()
    assert settings["local_login_enabled"] is True
    assert settings["local_login_locked"] is True
    # The switch is read-only while the override is set.
    assert _disable(admin).status_code == 409


def test_env_false_forces_it_off(auth_harness, monkeypatch) -> None:
    admin = auth_harness.client()
    auth_harness.login(admin, OWNER)
    _set_override(monkeypatch, "false")
    assert admin.get("/api/auth/status").json()["local_login_available"] is False
    enable = admin.put("/api/settings/authentik", json={"local_login_enabled": True})
    assert enable.status_code == 409
    # Other settings still save; sending the pinned value is harmless.
    same = admin.put(
        "/api/settings/authentik", json={"scopes": "openid email", "local_login_enabled": False}
    )
    assert same.status_code == 200, same.text


def test_blank_env_means_unset(auth_harness, monkeypatch) -> None:
    _set_override(monkeypatch, "")
    client = auth_harness.client()
    assert client.get("/api/auth/status").json()["local_login_available"] is True


def test_unverified_email_collision_redirects_instead_of_crashing(auth_harness) -> None:
    from urllib.parse import parse_qs, urlparse

    client = auth_harness.client()
    _onboard(client, email=OWNER["email"])
    # Same email as the local admin, but Authentik did not mark it verified.
    auth_harness.claims.clear()
    auth_harness.claims.update(OWNER)
    start = client.get("/api/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    done = client.get(f"/api/auth/callback?code=c&state={state}", follow_redirects=False)
    assert done.status_code == 302
    assert done.headers["location"] == "/?auth_error=email_conflict"
