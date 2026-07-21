"""All communication with the local Ollama instance lives here."""

import json
from collections.abc import Iterator
from typing import Any

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "You are Mathom, a careful local archivist. You help the user make sense of "
    "their recorded conversations and memories. Be warm, concise, and factual; "
    "never invent details that are not in the transcript."
)

# Human-readable names for the language codes faster-whisper reports, so the
# language directive reads naturally in the prompt. Unknown codes fall back to
# the raw code, which the model still handles well.
LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "cs": "Czech",
    "tr": "Turkish",
    "ar": "Arabic",
    "he": "Hebrew",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}


def language_directive(language: str | None) -> str | None:
    """Build a system-prompt instruction to answer in the detected language.

    Returns None when no language is known, so callers can leave the model to
    its default behaviour.
    """
    if not language:
        return None
    code = language.strip().lower()
    if not code:
        return None
    name = LANGUAGE_NAMES.get(code, language.strip())
    return (
        f"Always write your entire response in {name}, matching the language of "
        "the recording. Do this even if these instructions or the prompt template "
        "are written in another language."
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


def chat(messages: list[dict[str, str]], language: str | None = None) -> str:
    """Send a chat request to Ollama and return the assistant reply text.

    When ``language`` is given, the model is instructed to answer in that
    language so replies match the language of the recording.
    """
    settings = get_settings()
    system = SYSTEM_PROMPT
    directive = language_directive(language)
    if directive:
        system = f"{SYSTEM_PROMPT}\n\n{directive}"
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": False,
    }
    with _client() as client:
        response = client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    return str(data.get("message", {}).get("content", "")).strip()


def generate_summary(transcript: str, prompt_template: str, language: str | None = None) -> str:
    """Render a prompt template against a transcript and ask Ollama for output."""
    prompt = prompt_template.replace("{transcript}", transcript)
    return chat([{"role": "user", "content": prompt}], language=language)


def followup_chat(
    transcript: str,
    history: list[dict[str, str]],
    message: str,
    language: str | None = None,
) -> str:
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
    return chat(messages, language=language)


def stream_chat(messages: list[dict[str, str]], language: str | None = None) -> Iterator[str]:
    """Yield chat tokens from Ollama's newline-delimited streaming API."""
    settings = get_settings()
    system = SYSTEM_PROMPT
    directive = language_directive(language)
    if directive:
        system = f"{SYSTEM_PROMPT}\n\n{directive}"
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": True,
    }
    with _client() as client, client.stream("POST", "/api/chat", json=payload) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            token = str(data.get("message", {}).get("content", ""))
            if token:
                yield token


def stream_generate_summary(
    transcript: str, prompt_template: str, language: str | None = None
) -> Iterator[str]:
    """Yield a rendered summary as Ollama produces it."""
    prompt = prompt_template.replace("{transcript}", transcript)
    yield from stream_chat([{"role": "user", "content": prompt}], language=language)


def stream_followup_chat(
    transcript: str,
    history: list[dict[str, str]],
    message: str,
    language: str | None = None,
) -> Iterator[str]:
    """Yield a transcript-grounded follow-up reply."""
    context = (
        "Here is the transcript of the recording this conversation is about:\n\n"
        f"---\n{transcript}\n---\n\nAnswer the user's questions about this recording."
    )
    yield from stream_chat(
        [{"role": "user", "content": context}, *history, {"role": "user", "content": message}],
        language=language,
    )


def generate_title(transcript: str, language: str | None = None) -> str:
    """Create a short archival title without delaying summary generation."""
    title = generate_summary(
        transcript,
        "Give this recording a short, specific title (six words or fewer). Return only the title.",
        language,
    )
    return " ".join(title.split())[:300]
