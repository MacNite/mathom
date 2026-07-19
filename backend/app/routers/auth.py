"""Authentik SSO endpoints: login redirect, OAuth callback, logout, status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import optional_user
from app.models import User
from app.schemas import AuthStatus, LocalLogin, OnboardingCreate, UserOut
from app.services import auth, oidc
from app.services.passwords import hash_password, validate_password
from app.services.settings_store import AuthentikConfig, get_authentik_config

logger = logging.getLogger("mathom.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_PATH = "/auth/login"  # relative to the /api prefix


def _redirect_uri(request: Request, config: AuthentikConfig) -> str:
    base = config.public_base_url or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/callback"


def _safe_next(value: str | None) -> str:
    """Only allow same-site relative redirects (guards against open redirect)."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


@router.get("/status", response_model=AuthStatus)
def auth_status(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
) -> AuthStatus:
    settings = get_settings()
    config = get_authentik_config(db)
    return AuthStatus(
        auth_enabled=settings.auth_enabled,
        configured=config.configured,
        authenticated=user is not None,
        onboarding_required=settings.auth_enabled
        and int(db.execute(select(func.count(User.id))).scalar_one()) == 0,
        local_login_available=settings.auth_enabled,
        authentik_configured=config.configured,
        login_url="/api/auth/login/authentik",
        user=UserOut.model_validate(user) if user is not None else None,
    )


@router.get("/login")
def login_legacy(
    request: Request, next: str = "/", db: Session = Depends(get_db)
) -> RedirectResponse:
    return login_authentik(request, next, db)


@router.get("/login/authentik")
def login_authentik(
    request: Request, next: str = "/", db: Session = Depends(get_db)
) -> RedirectResponse:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="User management is disabled")
    config = get_authentik_config(db)
    if not config.configured:
        raise HTTPException(status_code=503, detail="Authentik is not configured yet")
    state = auth.create_oauth_state(db, _safe_next(next))
    try:
        url = oidc.build_authorize_url(
            config,
            state=state.state,
            nonce=state.nonce,
            redirect_uri=_redirect_uri(request, config),
        )
    except oidc.OIDCError as exc:
        logger.warning("Authentik login could not start: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach Authentik") from exc
    return RedirectResponse(url, status_code=302)


@router.post("/onboarding", response_model=UserOut, status_code=201)
def onboarding(
    payload: OnboardingCreate, request: Request, db: Session = Depends(get_db)
) -> Response:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(404, "User management is disabled")
    if payload.password != payload.password_confirmation:
        raise HTTPException(422, "Passwords do not match")
    try:
        validate_password(payload.password)
        # SQLite BEGIN IMMEDIATE serializes competing first-start writers.
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        if int(db.execute(select(func.count(User.id))).scalar_one()) != 0:
            db.rollback()
            raise HTTPException(409, "Onboarding has already completed")
        user = User(
            email=payload.email.strip().lower(),
            name=payload.name.strip(),
            role="admin",
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Onboarding has already completed") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session = auth.create_session(db, user)
    response = Response(
        content=UserOut.model_validate(user).model_dump_json(),
        media_type="application/json",
        status_code=201,
    )
    _set_session_cookie(response, session.token)
    return response


@router.post("/login/local", response_model=UserOut)
def login_local(payload: LocalLogin, db: Session = Depends(get_db)) -> Response:
    if not get_settings().auth_enabled:
        raise HTTPException(404, "User management is disabled")
    user = auth.local_login(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "Invalid email or password")
    session = auth.create_session(db, user)
    response = Response(
        content=UserOut.model_validate(user).model_dump_json(), media_type="application/json"
    )
    _set_session_cookie(response, session.token)
    return response


@router.get("/callback")
def callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="User management is disabled")
    if error:
        logger.info("Authentik returned an error: %s", error)
        return RedirectResponse(f"/?auth_error={error}", status_code=302)
    if not code or not state:
        return RedirectResponse("/?auth_error=invalid_request", status_code=302)

    stored_state = auth.pop_oauth_state(db, state)
    if stored_state is None:
        return RedirectResponse("/?auth_error=expired", status_code=302)

    config = get_authentik_config(db)
    try:
        tokens = oidc.exchange_code(config, code=code, redirect_uri=_redirect_uri(request, config))
        claims = oidc.fetch_userinfo(config, access_token=tokens.get("access_token", ""))
    except oidc.OIDCError as exc:
        logger.warning("Authentik callback failed: %s", exc)
        return RedirectResponse("/?auth_error=exchange_failed", status_code=302)

    # Bind the login to the nonce we issued. When Authentik returns an ID token
    # (it does for the openid scope) a mismatch means a replayed/injected token,
    # so reject it. If no nonce is present we fall back to the state check that
    # already succeeded above.
    token_nonce = oidc.id_token_nonce(tokens.get("id_token", ""))
    if token_nonce is not None and token_nonce != stored_state.nonce:
        logger.warning("Authentik callback rejected: nonce mismatch")
        return RedirectResponse("/?auth_error=invalid_nonce", status_code=302)

    user = auth.upsert_user_from_claims(db, claims, auto_create=config.auto_create_users)
    if user is None:
        return RedirectResponse("/?auth_error=not_provisioned", status_code=302)
    if not user.is_active:
        return RedirectResponse("/?auth_error=account_disabled", status_code=302)

    session = auth.create_session(db, user)
    response = RedirectResponse(_safe_next(stored_state.redirect_to), status_code=302)
    _set_session_cookie(response, session.token)
    return response


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    token = request.cookies.get(get_settings().session_cookie_name)
    auth.delete_session(db, token)
    response = Response(status_code=204)
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return response
