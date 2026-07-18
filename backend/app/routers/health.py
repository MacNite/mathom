from fastapi import APIRouter

from app.schemas import HealthOut
from app.services import ollama

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=VERSION, ollama_reachable=ollama.is_reachable())
