"""Manage personal API tokens (signed-in users, or the local user)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import ApiToken, User
from app.schemas import ApiTokenCreate, ApiTokenCreated, ApiTokenOut
from app.services import api_tokens

router = APIRouter(prefix="/tokens", tags=["tokens"])


def _user_id(user: User | None) -> int | None:
    return user.id if user is not None else None


@router.get("", response_model=list[ApiTokenOut])
def list_tokens(
    db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> list[ApiToken]:
    return api_tokens.list_for(db, _user_id(user))


@router.post("", response_model=ApiTokenCreated, status_code=201)
def create_token(
    payload: ApiTokenCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> ApiTokenCreated:
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Give the token a name")
    token, plaintext = api_tokens.create(db, _user_id(user), payload.name, payload.expires_in_days)
    return ApiTokenCreated(**ApiTokenOut.model_validate(token).model_dump(), token=plaintext)


@router.delete("/{token_id}", status_code=204)
def delete_token(
    token_id: int, db: Session = Depends(get_db), user: User | None = Depends(current_user)
) -> Response:
    if not api_tokens.delete(db, _user_id(user), token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    return Response(status_code=204)
