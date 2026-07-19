"""Background processing pipeline: pending → transcribing → summarizing → ready."""

import logging
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.db import get_session_factory, refresh_fts
from app.models import Mathom, PromptTemplate, Summary
from app.services import ollama, transcription

logger = logging.getLogger("mathom.pipeline")

# Statuses that only exist while a job is actively running in this process.
# After a restart no such job can still be running, so any Mathom left in one
# of these states was interrupted.
_IN_FLIGHT_STATUSES = ("pending", "transcribing", "summarizing")

INTERRUPTED_MESSAGE = (
    "Processing was interrupted before it finished (the server restarted). "
    "Re-run the summary to try again."
)


def _set_status(mathom_id: int, status: str, error: str | None = None) -> None:
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None:
            return
        mathom.status = status
        mathom.error_message = error
        session.commit()


def _safe_error(exc: Exception) -> str:
    """Map an internal failure to a calm, user-facing message.

    Raw exception text can contain file paths, model internals, or upstream
    error bodies, so it is logged server-side but never surfaced to the API.
    """
    from subprocess import SubprocessError

    from httpx import HTTPError

    if isinstance(exc, transcription.AudioValidationError):
        return "This file could not be read as audio. Please upload a valid recording."
    if isinstance(exc, SubprocessError):
        return "The recording could not be transcribed. It may be corrupt or unsupported."
    if isinstance(exc, HTTPError):
        return "The local AI model could not be reached. Check that Ollama is running."
    return "Processing failed unexpectedly. See the server logs for details."


def recover_interrupted_jobs() -> int:
    """Mark jobs left mid-flight by a crash/restart as errored.

    ``BackgroundTasks`` run in-process, so after a restart nothing is still
    working on these rows. Rather than leave them spinning forever, flip them
    to ``error`` with a clear, retryable message. Returns the number reset.
    """
    with get_session_factory()() as session:
        result = session.execute(
            update(Mathom)
            .where(Mathom.status.in_(_IN_FLIGHT_STATUSES))
            .values(status="error", error_message=INTERRUPTED_MESSAGE)
        )
        session.commit()
        count = int(result.rowcount or 0)
    if count:
        logger.warning("Reset %d interrupted job(s) to error after restart", count)
    return count


def process_mathom(mathom_id: int, template_slug: str = "general-summary") -> None:
    """Run the full pipeline for one Mathom. Safe to call in a background task."""
    factory = get_session_factory()
    try:
        _set_status(mathom_id, "transcribing")
        with factory() as session:
            mathom = session.get(Mathom, mathom_id)
            if mathom is None:
                return
            audio_path = Path(mathom.audio_path)

        # Reject spoofed uploads (right extension, non-audio bytes) before they
        # ever reach whisper.
        transcription.validate_audio(audio_path)

        with factory() as session:
            mathom = session.get(Mathom, mathom_id)
            if mathom is None:
                return
            mathom.duration_seconds = transcription.probe_duration_seconds(audio_path)
            session.commit()

        text, language = transcription.transcribe(audio_path)

        with factory() as session:
            mathom = session.get(Mathom, mathom_id)
            if mathom is None:
                return
            mathom.transcript = text
            mathom.language = language
            mathom.status = "summarizing"
            session.commit()
            refresh_fts(session, mathom_id)
            session.commit()

        summarize_mathom(mathom_id, template_slug)
        _set_status(mathom_id, "ready")
    except Exception as exc:  # noqa: BLE001 — pipeline must record any failure
        logger.exception("Pipeline failed for mathom %s", mathom_id)
        _set_status(mathom_id, "error", _safe_error(exc))


def summarize_mathom(mathom_id: int, template_slug: str) -> Summary | None:
    """Generate one summary for a Mathom with the given template. Returns it."""
    settings = get_settings()
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None or not mathom.transcript:
            return None
        template = session.execute(
            select(PromptTemplate).where(PromptTemplate.slug == template_slug)
        ).scalar_one_or_none()
        if template is None:
            template = session.execute(
                select(PromptTemplate).where(PromptTemplate.slug == "general-summary")
            ).scalar_one_or_none()
        if template is None:
            return None
        content = ollama.generate_summary(
            mathom.transcript, template.prompt, language=mathom.language
        )
        summary = Summary(
            mathom_id=mathom_id,
            template_slug=template.slug,
            template_name=template.name,
            content=content,
            model=settings.ollama_model,
        )
        session.add(summary)
        session.commit()
        refresh_fts(session, mathom_id)
        session.commit()
        session.refresh(summary)
        return summary
