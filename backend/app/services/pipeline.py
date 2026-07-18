"""Background processing pipeline: pending → transcribing → summarizing → ready."""

import logging
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory, refresh_fts
from app.models import Mathom, PromptTemplate, Summary
from app.services import ollama, transcription

logger = logging.getLogger("mathom.pipeline")


def _set_status(mathom_id: int, status: str, error: str | None = None) -> None:
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        if mathom is None:
            return
        mathom.status = status
        mathom.error_message = error
        session.commit()


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
        _set_status(mathom_id, "error", str(exc)[:2000])


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
        content = ollama.generate_summary(mathom.transcript, template.prompt)
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
