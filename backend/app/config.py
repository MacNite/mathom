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
    max_upload_mb: int = 200
    allowed_audio_extensions: str = ".mp3,.m4a,.wav,.ogg,.opus,.flac,.webm,.mp4,.aac"

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
