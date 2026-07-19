"""Application configuration, sourced from environment variables only."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATHOM_", extra="ignore")

    data_dir: Path = Path("./data")
    templates_dir: Path = Path("./prompt-templates")
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 300.0
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    # Hard wall-clock ceiling for a single FFmpeg normalization run, so a
    # pathological upload cannot occupy a worker indefinitely.
    ffmpeg_timeout_seconds: float = 600.0
    max_upload_mb: int = 200
    allowed_audio_extensions: str = ".mp3,.m4a,.wav,.ogg,.opus,.flac,.webm,.mp4,.aac"

    # --- Optional user management + Authentik SSO ------------------------------
    # All auth is OFF by default: the stack behaves as a single-user local
    # archive unless MATHOM_AUTH_ENABLED is explicitly set to true.
    auth_enabled: bool = False
    session_cookie_name: str = "mathom_session"
    session_ttl_hours: int = 720  # 30 days
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
