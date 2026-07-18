"""All communication with the local Ollama instance lives here."""

from typing import Any

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "You are Mathom, a careful local archivist. You help the user make sense of "
    "their recorded conversations and memories. Be warm, concise, and factual; "
    "never invent details that are not in the transcript."
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
    with _client() as client:
        response = client.post("/api/chat", json=payload)
        response.raise_for_status()
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
