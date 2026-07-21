"""Background processing pipeline: pending → transcribing → summarizing → ready."""

import logging
from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, select, update

from app.config import get_settings
from app.db import get_session_factory, refresh_fts
from app.models import Mathom, PromptTemplate, Summary
from app.services import ollama, transcription
from app.services.diarization import label_segments
from app.services.template_localization import localized_prompt

logger = logging.getLogger("mathom.pipeline")

# Statuses a Mathom can hold while work is outstanding. After a restart these
# are only legitimate if a queued/running job still owns the Mathom; otherwise
# the Mathom was orphaned and is flipped to error.
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


def mark_error(mathom_id: int, exc: Exception) -> None:
    """Record a failed pipeline run as a calm, user-facing error."""
    _set_status(mathom_id, "error", _safe_error(exc))


def recover_interrupted_jobs() -> int:
    """Flip orphaned in-flight Mathoms to error after a restart.

    A Mathom is orphaned when it sits in an in-flight status but no queued or
    running job owns it — its worker died mid-run. Mathoms that still have a
    live job are left alone; the worker resumes them. Returns the number reset.
    """
    from app.models import Job

    with get_session_factory()() as session:
        active = select(Job.mathom_id).where(Job.status.in_(("queued", "running")))
        result = cast(
            "CursorResult[Any]",
            session.execute(
                update(Mathom)
                .where(Mathom.status.in_(_IN_FLIGHT_STATUSES), Mathom.id.not_in(active))
                .values(status="error", error_message=INTERRUPTED_MESSAGE)
            ),
        )
        session.commit()
        count = int(result.rowcount or 0)
    if count:
        logger.warning("Flipped %d orphaned Mathom(s) to error after restart", count)
    return count


def run(mathom_id: int, template_slug: str = "general-summary") -> None:
    """Run the full pipeline for one Mathom, raising on any failure.

    The durable worker calls this so it can decide whether to retry. Callers
    that want failures recorded (not raised) should use ``process_mathom``.
    """
    factory = get_session_factory()
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

    text, language, segments = transcription.transcribe(audio_path)

    with factory() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None:
            return
        mathom.transcript = text
        mathom.language = language
        mathom.segments = label_segments(segments)
        mathom.status = "summarizing"
        session.commit()
        refresh_fts(session, mathom_id)
        session.commit()

    # A title is independent from the summary and intentionally cheap.
    with factory() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is not None and mathom.title == "Untitled Mathom":
            mathom.title = ollama.generate_title(text, language) or mathom.title
            session.commit()
            refresh_fts(session, mathom_id)
            session.commit()

    summarize_mathom(mathom_id, template_slug)
    _set_status(mathom_id, "ready")


def process_mathom(mathom_id: int, template_slug: str = "general-summary") -> None:
    """Run the pipeline inline, recording any failure as an error status."""
    try:
        run(mathom_id, template_slug)
    except Exception as exc:  # noqa: BLE001 — pipeline must record any failure
        logger.exception("Pipeline failed for mathom %s", mathom_id)
        mark_error(mathom_id, exc)


def summarize_mathom(
    mathom_id: int, template_slug: str, template_language: str | None = None
) -> Summary | None:
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
        prompt = localized_prompt(template, template_language or mathom.template_language)
        if len(mathom.transcript) > settings.summary_chunk_chars:
            chunks = [
                mathom.transcript[index : index + settings.summary_chunk_chars]
                for index in range(0, len(mathom.transcript), settings.summary_chunk_chars)
            ]
            partials = [
                ollama.generate_summary(chunk, prompt, language=mathom.language) for chunk in chunks
            ]
            content = ollama.generate_summary(
                "\n\n".join(partials),
                "Combine these partial summaries into one coherent result:\n{transcript}",
                language=mathom.language,
            )
        else:
            content = ollama.generate_summary(mathom.transcript, prompt, language=mathom.language)
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
