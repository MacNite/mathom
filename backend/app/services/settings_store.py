"""Owner-editable Authentik/OIDC settings.

Connection details are seeded from environment variables on first use and then
kept in the ``app_settings`` table so the Owner can adjust them in the UI
without touching the container. The database copy, once written, is
authoritative; unset keys fall back to the environment defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSetting

_PREFIX = "authentik."
_STR_KEYS = ("issuer", "client_id", "client_secret", "scopes", "public_base_url")
_BOOL_KEYS = ("auto_create_users", "verify_ssl", "local_login_enabled")


@dataclass
class AuthentikConfig:
    issuer: str
    client_id: str
    client_secret: str
    scopes: str
    public_base_url: str
    auto_create_users: bool
    verify_ssl: bool
    # The admin's "Allow password sign-in" switch. Use ``local_login_enabled()``
    # for the effective value: the environment can override it.
    local_login_enabled: bool = True

    @property
    def configured(self) -> bool:
        """True once enough is set to attempt an OIDC login."""
        return bool(self.issuer and self.client_id and self.client_secret)


def _read(session: Session) -> dict[str, str]:
    rows = session.execute(
        select(AppSetting.key, AppSetting.value).where(AppSetting.key.like(f"{_PREFIX}%"))
    ).all()
    return {key[len(_PREFIX) :]: value for key, value in rows}


def get_authentik_config(session: Session) -> AuthentikConfig:
    settings = get_settings()
    stored = _read(session)

    def s(key: str, default: str) -> str:
        return stored.get(key, default)

    def b(key: str, default: bool) -> bool:
        if key in stored:
            return stored[key] == "true"
        return default

    return AuthentikConfig(
        issuer=s("issuer", settings.authentik_issuer).rstrip("/"),
        client_id=s("client_id", settings.authentik_client_id),
        client_secret=s("client_secret", settings.authentik_client_secret),
        scopes=s("scopes", settings.authentik_scopes),
        public_base_url=s("public_base_url", settings.public_base_url).rstrip("/"),
        auto_create_users=b("auto_create_users", settings.auth_auto_create_users),
        verify_ssl=b("verify_ssl", settings.oidc_verify_ssl),
        local_login_enabled=b("local_login_enabled", True),
    )


def local_login_override() -> bool | None:
    """The ``MATHOM_LOCAL_LOGIN_ENABLED`` override, or None when unset."""
    return get_settings().local_login_enabled


def local_login_enabled(session: Session) -> bool:
    """Whether email + password sign-in is currently allowed."""
    if not get_settings().auth_enabled:
        return False
    override = local_login_override()
    if override is not None:
        return override
    return get_authentik_config(session).local_login_enabled


def _set(session: Session, key: str, value: str) -> None:
    full = f"{_PREFIX}{key}"
    setting = session.get(AppSetting, full)
    if setting is None:
        session.add(AppSetting(key=full, value=value))
    else:
        setting.value = value


def update_authentik_config(session: Session, updates: dict[str, object]) -> AuthentikConfig:
    """Persist a partial update. ``client_secret`` is only written when a
    non-empty value is provided, so the UI can leave it blank to keep it."""
    for key in _STR_KEYS:
        if key in updates and updates[key] is not None:
            value = str(updates[key]).strip()
            if key == "client_secret" and value == "":
                continue
            _set(session, key, value)
    for key in _BOOL_KEYS:
        if key in updates and updates[key] is not None:
            _set(session, key, "true" if updates[key] else "false")
    session.commit()
    return get_authentik_config(session)


_SMTP_PREFIX = "smtp."
_SMTP_STR_KEYS = ("host", "username", "password", "from_email", "from_name", "public_base_url")
_SMTP_INT_KEYS = ("port", "invite_expiry_hours")
_SMTP_BOOL_KEYS = ("use_tls",)


@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    public_base_url: str
    use_tls: bool
    invite_expiry_hours: int

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.from_email)


def get_smtp_config(session: Session) -> SmtpConfig:
    settings = get_settings()
    stored = {
        key[len(_SMTP_PREFIX) :]: value for key, value in _read_all(session, _SMTP_PREFIX).items()
    }

    def s(key: str, default: str) -> str:
        return stored.get(key, default)

    def i(key: str, default: int) -> int:
        try:
            return int(stored.get(key, str(default)))
        except ValueError:
            return default

    return SmtpConfig(
        host=s("host", settings.smtp_host),
        port=i("port", settings.smtp_port),
        username=s("username", settings.smtp_username),
        password=s("password", settings.smtp_password),
        from_email=s("from_email", settings.smtp_from_email),
        from_name=s("from_name", settings.smtp_from_name),
        public_base_url=s("public_base_url", settings.public_base_url).rstrip("/"),
        use_tls=s("use_tls", "true" if settings.smtp_use_tls else "false") == "true",
        invite_expiry_hours=max(
            1, min(i("invite_expiry_hours", settings.invite_expiry_hours), 720)
        ),
    )


def _read_all(session: Session, prefix: str) -> dict[str, str]:
    return dict(
        session.execute(
            select(AppSetting.key, AppSetting.value).where(AppSetting.key.like(f"{prefix}%"))
        )
        .tuples()
        .all()
    )


def update_smtp_config(session: Session, updates: dict[str, object]) -> SmtpConfig:
    for key in _SMTP_STR_KEYS:
        if key in updates and updates[key] is not None:
            value = str(updates[key]).strip()
            if key == "password" and not value:
                continue
            _set_prefixed(session, _SMTP_PREFIX, key, value)
    for key in _SMTP_INT_KEYS:
        if key in updates and updates[key] is not None:
            _set_prefixed(session, _SMTP_PREFIX, key, str(updates[key]))
    for key in _SMTP_BOOL_KEYS:
        if key in updates and updates[key] is not None:
            _set_prefixed(session, _SMTP_PREFIX, key, "true" if updates[key] else "false")
    session.commit()
    return get_smtp_config(session)


def _set_prefixed(session: Session, prefix: str, key: str, value: str) -> None:
    setting = session.get(AppSetting, f"{prefix}{key}")
    if setting is None:
        session.add(AppSetting(key=f"{prefix}{key}", value=value))
    else:
        setting.value = value
