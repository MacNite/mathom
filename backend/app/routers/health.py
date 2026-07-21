from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthOut
from app.services import ollama, vision

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    installed = capable = None
    if settings.vision_enabled:
        try:
            vision._show()
            installed = capable = True
        except vision.VisionError:
            installed = capable = False
    return HealthOut(
        status="ok",
        version=VERSION,
        ollama_reachable=ollama.is_reachable(),
        vision_enabled=settings.vision_enabled,
        vision_model=settings.vision_model,
        vision_model_installed=installed,
        vision_model_has_vision=capable,
    )
