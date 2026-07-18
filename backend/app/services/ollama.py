"""All communication with the local Ollama instance lives here."""

from typing import Any

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "You are Mathom, a careful local archivist. You help the user make sense of "
    "their recorded conversations and memories. Be warm, concise, and factual; "
    "never invent details that are not in the transcript."
)


class OllamaError(RuntimeError):
    """A call to the local Ollama service failed in a way worth surfacing to the user."""


class OllamaModelNotFoundError(OllamaError):
    """Ollama is reachable but the configured model has not been pulled yet."""

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(
            f"The Ollama model '{model}' isn't installed yet. Pull it once with "
            "`make models` (or `scripts/pull-model.sh`), then try again."
        )


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.ollama_base_url,
        timeout=httpx.Timeout(settings.ollama_timeout_seconds, connect=10.0),
    )


def is_reachable() -> bool:
    try:
        with _client() as client:
            return client.get("/api/version", timeout=5.0).status_code == 200
    except httpx.HTTPError:
        return False


def chat(messages: list[dict[str, str]]) -> str:
    """Send a chat request to Ollama and return the assistant reply text."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "stream": False,
    }
    try:
        with _client() as client:
            response = client.post("/api/chat", json=payload)
    except httpx.HTTPError as exc:
        raise OllamaError(
            f"Couldn't reach Ollama at {settings.ollama_base_url}. "
            "Is the Ollama service running?"
        ) from exc
    # Ollama answers /api/chat with 404 when the requested model has never been
    # pulled — translate that into an actionable message instead of a raw HTTP error.
    if response.status_code == 404:
        raise OllamaModelNotFoundError(settings.ollama_model)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OllamaError(
            f"Ollama returned an error ({response.status_code}) for the chat request."
        ) from exc
    data = response.json()
    return str(data.get("message", {}).get("content", "")).strip()


def generate_summary(transcript: str, prompt_template: str) -> str:
    """Render a prompt template against a transcript and ask Ollama for output."""
    prompt = prompt_template.replace("{transcript}", transcript)
    return chat([{"role": "user", "content": prompt}])


def followup_chat(transcript: str, history: list[dict[str, str]], message: str) -> str:
    """Answer a follow-up question grounded in the transcript plus chat history."""
    context = (
        "Here is the transcript of the recording this conversation is about:\n\n"
        f"---\n{transcript}\n---\n\n"
        "Answer the user's questions about this recording."
    )
    messages = [
        {"role": "user", "content": context},
        *history,
        {"role": "user", "content": message},
    ]
    return chat(messages)
