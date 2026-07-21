"""Background processing pipeline: pending → transcribing → summarizing → ready."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, select, update

from app.config import get_settings
from app.db import get_session_factory, refresh_fts
from app.models import Mathom, PromptTemplate, Summary
from app.services import documents, ollama, transcription, vision
from app.services.diarization import label_segments
from app.services.template_localization import localized_prompt

logger = logging.getLogger("mathom.pipeline")

COMBINE_SUMMARIES_PROMPT = "Combine these partial summaries into one coherent result:\n{transcript}"

# Statuses a Mathom can hold while work is outstanding. After a restart these
# are only legitimate if a queued/running job still owns the Mathom; otherwise
# the Mathom was orphaned and is flipped to error.
_IN_FLIGHT_STATUSES = ("pending", "transcribing", "analyzing_visuals", "summarizing")

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
    if isinstance(exc, documents.DocumentExtractionError):
        return str(exc)
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
        source_type = mathom.source_type
        audio_path = Path(mathom.audio_path)
        source_path = Path(mathom.source_path)

    if source_type in {"audio", "video"} and mathom.has_audio_stream:
        transcription.validate_audio(audio_path)
        with factory() as session:
            mathom = session.get(Mathom, mathom_id)
            if mathom is None:
                return
            mathom.duration_seconds = transcription.probe_duration_seconds(audio_path)
            session.commit()
        text, language, segments = transcription.transcribe(audio_path)
        segments = label_segments(segments, audio_path)
    elif source_type == "document":
        text = documents.extract_text(source_path, source_path.suffix.lower())
        language, segments = None, []
    elif source_type == "text":
        with factory() as session:
            mathom = session.get(Mathom, mathom_id)
            if mathom is None or not mathom.transcript:
                return
            text = mathom.transcript
        language, segments = None, []
    elif source_type == "video":
        text, language, segments = "", None, []
    else:
        raise ValueError("unknown source type")

    with factory() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None:
            return
        mathom.transcript = text
        mathom.language = language
        mathom.segments = segments
        mathom.status = "analyzing_visuals" if mathom.vision_requested else "summarizing"
        session.commit()
        refresh_fts(session, mathom_id)
        session.commit()

    if source_type == "video" and mathom.vision_requested:
        try:
            observations, visual_summary, vision_status = vision.analyze(
                source_path or audio_path, mathom.duration_seconds
            )
            with factory() as session:
                current = session.get(Mathom, mathom_id)
                if current is not None:
                    current.visual_observations = observations
                    current.visual_summary = visual_summary
                    current.vision_status = vision_status
                    current.vision_processed_at = datetime.now(UTC)
                    current.status = "summarizing"
                    refresh_fts(session, mathom_id)
                    session.commit()
        except Exception:
            logger.exception("Visual analysis failed for mathom %s", mathom_id)
            with factory() as session:
                current = session.get(Mathom, mathom_id)
                if current is not None:
                    current.vision_status = "error"
                    current.vision_error_message = (
                        "Visual analysis could not be completed. You can try again."
                    )
                    session.commit()
            if not text:
                raise
    # A title is independent from the summary and intentionally cheap.
    with factory() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is not None and mathom.title == "Untitled Mathom":
            mathom.title = ollama.generate_title(build_context(mathom), language) or mathom.title
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


def run_visual_analysis(mathom_id: int) -> None:
    """Refresh visual evidence only; never retranscribe or replace summaries."""
    factory = get_session_factory()
    with factory() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None or not mathom.has_video_stream:
            raise ValueError("visual analysis requires a video")
        source = Path(mathom.source_path or mathom.audio_path)
        duration = mathom.duration_seconds
        mathom.vision_status = "processing"
        session.commit()
    observations, visual_summary, status = vision.analyze(source, duration)
    with factory() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None:
            return
        mathom.visual_observations = observations
        mathom.visual_summary = visual_summary
        mathom.vision_status = status
        mathom.vision_error_message = None
        mathom.vision_processed_at = datetime.now(UTC)
        refresh_fts(session, mathom_id)
        session.commit()


def summarize_mathom(
    mathom_id: int, template_slug: str, template_language: str | None = None
) -> Summary | None:
    """Generate one summary for a Mathom with the given template. Returns it."""
    settings = get_settings()
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None or not build_context(mathom):
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
        summary_input, summary_prompt = prepare_summary_input(
            build_context(mathom), prompt, mathom.language, settings.summary_chunk_chars
        )
        content = ollama.generate_summary(summary_input, summary_prompt, language=mathom.language)
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


def build_context(mathom: Mathom) -> str:
    """One explicit model/search/export context; never changes spoken transcript."""
    if not mathom.visual_summary and not mathom.visual_observations:
        return mathom.transcript or ""
    parts: list[str] = []
    if mathom.transcript:
        parts.append("--- Spoken transcript ---\n" + mathom.transcript)
    if mathom.visual_summary:
        parts.append(
            "--- Visual summary (sampled frames; AI-generated) ---\n" + mathom.visual_summary
        )
    if mathom.visual_observations:
        parts.append(
            "--- Visual observations (sampled frames; AI-generated) ---\n"
            + str(mathom.visual_observations)
        )
    return "\n\n".join(parts)


def prepare_summary_input(
    transcript: str,
    prompt: str,
    language: str | None,
    chunk_chars: int | None = None,
) -> tuple[str, str]:
    """Return the final summary input, mapping long transcripts into partials.

    Both HTTP streaming and background summaries use this policy. The map step
    deliberately finishes before the final request, which can then be streamed
    without exposing an overlong transcript to Ollama.
    """
    threshold = chunk_chars if chunk_chars is not None else get_settings().summary_chunk_chars
    if len(transcript) <= threshold:
        return transcript, prompt
    chunks = [
        transcript[index : index + threshold] for index in range(0, len(transcript), threshold)
    ]
    partials = [ollama.generate_summary(chunk, prompt, language=language) for chunk in chunks]
    return "\n\n".join(partials), COMBINE_SUMMARIES_PROMPT
