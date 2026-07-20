"""Administrator invitation lifecycle and public registration acceptance."""

from datetime import timedelta
from smtplib import SMTPException

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Invitation, User, as_aware, utcnow
from app.schemas import InvitationAccept, InvitationCreate, InvitationOut, UserOut
from app.services.invitations import new_token, send_invitation, token_hash
from app.services.passwords import hash_password, validate_password
from app.services.settings_store import get_smtp_config

router = APIRouter(prefix="/invitations", tags=["invitations"])


def normalize(email: str) -> str:
    return email.strip().lower()


@router.get("", response_model=list[InvitationOut])
def list_invitations(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[Invitation]:
    return list(db.execute(select(Invitation).order_by(Invitation.created_at.desc())).scalars())


@router.post("", response_model=InvitationOut, status_code=201)
def create_invitation(
    payload: InvitationCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> Invitation:
    email = normalize(payload.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(409, "Email address is already in use")
    existing = db.scalar(select(Invitation).where(Invitation.email == email))
    if (
        existing
        and existing.accepted_at is None
        and existing.revoked_at is None
        and as_aware(existing.expires_at) > utcnow()
    ):
        raise HTTPException(409, "An active invitation already exists for this email address")
    if existing:
        db.delete(existing)
        db.flush()
    config = get_smtp_config(db)
    token = new_token()
    invite = Invitation(
        email=email,
        name=payload.name.strip(),
        token_hash=token_hash(token),
        expires_at=utcnow() + timedelta(hours=config.invite_expiry_hours),
    )
    db.add(invite)
    try:
        send_invitation(config, email, invite.name, token)
    except (OSError, SMTPException, ValueError) as exc:
        db.rollback()
        raise HTTPException(503, f"Invitation was not sent: {exc}") from exc
    invite.sent_at = utcnow()
    db.commit()
    db.refresh(invite)
    return invite


@router.post("/{invite_id}/revoke", response_model=InvitationOut)
def revoke_invitation(
    invite_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> Invitation:
    invite = db.get(Invitation, invite_id)
    if not invite:
        raise HTTPException(404, "Invitation not found")
    if invite.accepted_at is not None:
        raise HTTPException(409, "Accepted invitations cannot be revoked")
    if invite.revoked_at is None:
        invite.revoked_at = utcnow()
        db.commit()
        db.refresh(invite)
    return invite


@router.delete("/{invite_id}", status_code=204)
def delete_invitation(
    invite_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> None:
    invite = db.get(Invitation, invite_id)
    if not invite:
        raise HTTPException(404, "Invitation not found")
    # An active, pending invitation still has a live token in someone's inbox.
    # Revoke it first so it cannot be accepted; only then may it be cleared.
    if (
        invite.accepted_at is None
        and invite.revoked_at is None
        and as_aware(invite.expires_at) > utcnow()
    ):
        raise HTTPException(409, "Revoke the invitation before deleting it")
    db.delete(invite)
    db.commit()


@router.post("/accept", response_model=UserOut)
def accept_invitation(payload: InvitationAccept, db: Session = Depends(get_db)) -> User:
    invite = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash(payload.token)))
    if (
        not invite
        or invite.revoked_at is not None
        or invite.accepted_at is not None
        or as_aware(invite.expires_at) <= utcnow()
    ):
        raise HTTPException(400, "This invitation is invalid, expired, or revoked")
    try:
        validate_password(payload.password)
        user = User(
            email=invite.email, name=invite.name, password_hash=hash_password(payload.password)
        )
        db.add(user)
        invite.accepted_at = utcnow()
        db.commit()
        db.refresh(user)
        return user
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Email address is already in use") from exc
