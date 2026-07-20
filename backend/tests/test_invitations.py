"""Invitation lifecycle: revoked/expired invitations can be cleared and re-sent.

Uses the ``auth_harness`` fixture (see conftest) to sign in an admin, and seeds
invitation rows directly so the tests need neither SMTP nor the network.
"""

from datetime import timedelta

OWNER = {"sub": "owner-sub", "email": "owner@example.com", "name": "Archive Owner"}
ALICE = {"sub": "alice-sub", "email": "alice@example.com", "name": "Alice"}


def _seed_invitation(**overrides: object) -> int:
    from app.db import get_session_factory
    from app.models import Invitation, utcnow
    from app.services.invitations import new_token, token_hash

    fields: dict[str, object] = dict(
        email="invitee@example.com",
        name="Invitee",
        token_hash=token_hash(new_token()),
        expires_at=utcnow() + timedelta(hours=48),
    )
    fields.update(overrides)
    with get_session_factory()() as session:
        invite = Invitation(**fields)  # type: ignore[arg-type]
        session.add(invite)
        session.commit()
        return int(invite.id)


def test_revoked_invitation_can_be_deleted(auth_harness) -> None:
    from app.models import utcnow

    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)

    invite_id = _seed_invitation(revoked_at=utcnow())
    assert owner.delete(f"/api/invitations/{invite_id}").status_code == 204
    # The row is gone, so it no longer appears in the listing.
    assert all(i["id"] != invite_id for i in owner.get("/api/invitations").json())


def test_expired_invitation_can_be_deleted(auth_harness) -> None:
    from app.models import utcnow

    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)

    invite_id = _seed_invitation(expires_at=utcnow() - timedelta(hours=1))
    assert owner.delete(f"/api/invitations/{invite_id}").status_code == 204


def test_active_invitation_must_be_revoked_before_deletion(auth_harness) -> None:
    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)

    invite_id = _seed_invitation()  # active + pending
    resp = owner.delete(f"/api/invitations/{invite_id}")
    assert resp.status_code == 409
    # It survives the rejected delete.
    assert any(i["id"] == invite_id for i in owner.get("/api/invitations").json())


def test_delete_requires_admin(auth_harness) -> None:
    from app.models import utcnow

    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    alice = auth_harness.client()
    auth_harness.login(alice, ALICE)  # first user is owner; Alice is a plain user

    invite_id = _seed_invitation(revoked_at=utcnow())
    assert alice.delete(f"/api/invitations/{invite_id}").status_code == 403


def test_missing_invitation_is_a_404(auth_harness) -> None:
    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)
    assert owner.delete("/api/invitations/999999").status_code == 404


def test_email_can_be_reinvited_after_a_revoked_invitation_is_deleted(auth_harness) -> None:
    """The whole point: clear a revoked invite, then re-send to the same email.

    The listing of a revoked-then-persisted invitation exercises the naive/aware
    datetime comparison, which used to raise a 500.
    """
    from app.models import utcnow

    owner = auth_harness.client()
    auth_harness.login(owner, OWNER)

    revoked_id = _seed_invitation(email="return@example.com", revoked_at=utcnow())
    # Listing must not blow up on the stored (naive) expiry.
    assert owner.get("/api/invitations").status_code == 200
    assert owner.delete(f"/api/invitations/{revoked_id}").status_code == 204

    # A fresh invitation for the same address is now unobstructed.
    reseeded = _seed_invitation(email="return@example.com")
    assert any(i["id"] == reseeded for i in owner.get("/api/invitations").json())
