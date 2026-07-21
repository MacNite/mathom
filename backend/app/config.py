"""Application configuration, sourced from environment variables only."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATHOM_", extra="ignore")

    data_dir: Path = Path("./data")
    templates_dir: Path = Path("./prompt-templates")
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 300.0
    # Bound the number of recordings waiting for the serial processing worker.
    # This is admission control, not a per-client rate limit: it keeps a burst
    # of large uploads from turning into an unbounded wait for everyone.
    max_queued_jobs: int = Field(default=25, ge=0)
    # Follow-up chat is interactive and intentionally remains synchronous, but
    # only this many requests may occupy Ollama at once.
    chat_concurrency: int = Field(default=1, ge=1)
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_initial_prompt: str = ""
    summary_chunk_chars: int = Field(default=24000, ge=1000)
    diarization_enabled: bool = False
    # Hard wall-clock ceiling for a single FFmpeg normalization run, so a
    # pathological upload cannot occupy a worker indefinitely.
    ffmpeg_timeout_seconds: float = 600.0
    max_upload_mb: int = 200
    allowed_audio_extensions: str = ".mp3,.m4a,.wav,.ogg,.opus,.flac,.webm,.mp4,.aac"

    # --- Rate limiting ---------------------------------------------------------
    # In-process, per-client fixed-window limiter. Protects the box from runaway
    # clients and brute-forcing the login. Disable only behind another limiter.
    rate_limit_enabled: bool = True
    # Budget for cheap reads (GET) per client per minute.
    rate_limit_per_minute: int = 120
    # Tighter budget for expensive work: uploads, chat, summaries, search, and
    # any auth/login attempt.
    rate_limit_heavy_per_minute: int = 20

    # --- Optional user management + Authentik SSO ------------------------------
    # All auth is OFF by default: the stack behaves as a single-user local
    # archive unless MATHOM_AUTH_ENABLED is explicitly set to true.
    auth_enabled: bool = False
    session_cookie_name: str = "mathom_session"
    # Absolute session lifetime. 14 days balances a friendly local-archive UX
    # against exposure of a stolen cookie; Authentik re-auth is quick. Tune via
    # MATHOM_SESSION_TTL_HOURS.
    session_ttl_hours: int = 336  # 14 days
    session_cookie_secure: bool = True
    # Public origin used to build the OAuth redirect URI, e.g.
    # https://mathom.example.com. Falls back to the request origin when empty.
    public_base_url: str = ""

    # Authentik / OIDC connection defaults. These seed the database-backed
    # settings on first run; the Owner can override them later in the UI.
    authentik_issuer: str = ""  # e.g. https://auth.example.com/application/o/mathom/
    authentik_client_id: str = ""
    authentik_client_secret: str = ""
    authentik_scopes: str = "openid profile email"
    oidc_verify_ssl: bool = True
    # Automatically provision a Mathom account the first time an Authentik user
    # signs in. When false an Owner/Admin must pre-create the account.
    auth_auto_create_users: bool = True
    # Email address that becomes the Owner on first sign-in. When empty the very
    # first user to sign in is made Owner.
    auth_owner_email: str = ""

    # SMTP defaults for invitation delivery. Values can be overridden by an admin.
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Mathom"
    smtp_use_tls: bool = False
    invite_expiry_hours: int = 168

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'mathom.db'}"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def allowed_extensions(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_audio_extensions.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
