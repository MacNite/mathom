"""Local profile and administrator user management."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import authenticated_user, require_admin
from app.models import ROLE_ADMIN, User
from app.schemas import PasswordChange, UserCreate, UserOut, UserUpdate
from app.services import auth
from app.services.passwords import hash_password, validate_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


def get(uid: int, db: Session) -> User:
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    return u


def admins(db: Session, exclude: int) -> int:
    return int(
        db.execute(
            select(func.count(User.id)).where(
                User.role == ROLE_ADMIN, User.is_active.is_(True), User.id != exclude
            )
        ).scalar_one()
    )


def normalize(email: str) -> str:
    return email.strip().lower()


def guard_admin(target: User, changes: dict, db: Session) -> None:
    if (
        target.role == ROLE_ADMIN
        and (changes.get("role") not in (None, ROLE_ADMIN) or changes.get("is_active") is False)
        and admins(db, target.id) == 0
    ):
        raise HTTPException(409, "Cannot remove the last active admin")


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.execute(select(User).order_by(User.created_at)).scalars())


@router.post("", response_model=UserOut, status_code=201)
def create(
    payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> User:
    try:
        validate_password(payload.password)
        u = User(
            email=normalize(payload.email),
            name=payload.name.strip(),
            role=payload.role,
            password_hash=hash_password(payload.password),
            must_change_password=payload.must_change_password,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Email address is already in use") from e


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(authenticated_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    changes.pop("role", None)
    changes.pop("is_active", None)
    if "email" in changes:
        changes["email"] = normalize(changes["email"])
    try:
        for k, v in changes.items():
            setattr(user, k, v)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Email address is already in use") from e


@router.post("/me/password", response_model=UserOut)
def change_password(
    payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> User:
    if user.password_hash and not verify_password(
        payload.current_password or "", user.password_hash
    ):
        raise HTTPException(400, "Current password is incorrect")
    try:
        user.password_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    user.must_change_password = False
    auth.revoke_sessions(db, user)
    db.add(user)
    db.commit()
    return user


@router.post("/me/sessions/revoke", status_code=204)
def revoke_me(db: Session = Depends(get_db), user: User = Depends(authenticated_user)) -> Response:
    auth.revoke_sessions(db, user)
    return Response(status_code=204)


@router.patch("/{user_id}", response_model=UserOut)
def update(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    target = get(user_id, db)
    changes = payload.model_dump(exclude_unset=True)
    guard_admin(target, changes, db)
    if "email" in changes:
        changes["email"] = normalize(changes["email"])
    try:
        for k, v in changes.items():
            setattr(target, k, v)
        if changes.get("is_active") is False:
            auth.revoke_sessions(db, target)
        db.commit()
        db.refresh(target)
        return target
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Email address is already in use") from e


@router.post("/{user_id}/password", response_model=UserOut)
def reset(
    user_id: int,
    payload: PasswordChange,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    target = get(user_id, db)
    try:
        target.password_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    target.must_change_password = True
    auth.revoke_sessions(db, target)
    db.add(target)
    db.commit()
    return target


@router.post("/{user_id}/sessions/revoke", status_code=204)
def revoke(
    user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    auth.revoke_sessions(db, get(user_id, db))
    return Response(status_code=204)


@router.delete("/{user_id}", status_code=204)
def delete(
    user_id: int, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> Response:
    target = get(user_id, db)
    if target.id == actor.id:
        raise HTTPException(409, "You cannot delete your own account")
    guard_admin(target, {"role": "user"}, db)
    db.delete(target)
    db.commit()
    return Response(status_code=204)
