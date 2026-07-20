"""Durable job queue backed by the ``jobs`` table.

A single worker thread (see ``services/worker.py``) claims queued jobs and runs
the pipeline. Persisting the work means it survives a restart — there is no
external broker, which keeps the local-first, one-stack design intact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.db import get_session_factory
from app.models import Job

# Retry backoff is exponential but capped so a flaky Ollama does not stall a
# recording for long.
_BASE_BACKOFF_SECONDS = 5
_MAX_BACKOFF_SECONDS = 60

_IN_FLIGHT = ("queued", "running")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def enqueue(session: Session, mathom_id: int, template_slug: str, kind: str = "process") -> Job:
    """Add a job for a Mathom. Commits within the caller's session."""
    job = Job(mathom_id=mathom_id, template_slug=template_slug, kind=kind, status="queued")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def has_active_job(session: Session, mathom_id: int) -> bool:
    return (
        session.execute(
            select(Job.id).where(Job.mathom_id == mathom_id, Job.status.in_(_IN_FLIGHT))
        ).first()
        is not None
    )


def queued_count(session: Session) -> int:
    """Return the number of recordings waiting to be claimed."""
    statement = select(func.count()).select_from(Job).where(Job.status == "queued")
    return int(session.scalar(statement) or 0)


def queue_position(session: Session, mathom_id: int) -> int | None:
    """Return a queued Mathom's one-based position, or None once it has started."""
    job = session.execute(
        select(Job)
        .where(Job.mathom_id == mathom_id, Job.status == "queued")
        .order_by(Job.available_at, Job.id)
        .limit(1)
    ).scalar_one_or_none()
    if job is None:
        return None
    earlier = session.execute(
        select(Job.id).where(
            Job.status == "queued",
            (Job.available_at < job.available_at)
            | ((Job.available_at == job.available_at) & (Job.id < job.id)),
        )
    ).all()
    return len(earlier) + 1


def claim_next(session: Session) -> Job | None:
    """Claim the oldest runnable job, marking it ``running``. None if idle.

    Only one worker runs, so a plain read-then-update is safe; the status guard
    keeps it correct even if that ever changes.
    """
    now = _now()
    job = session.execute(
        select(Job)
        .where(Job.status == "queued", Job.available_at <= now)
        .order_by(Job.available_at, Job.id)
        .limit(1)
    ).scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.started_at = now
    job.attempts += 1
    session.commit()
    session.refresh(job)
    return job


def complete(session: Session, job_id: int) -> None:
    session.execute(update(Job).where(Job.id == job_id).values(status="done", error_message=None))
    session.commit()


def retry_or_fail(session: Session, job_id: int, error: str) -> str:
    """Requeue a failed job with backoff, or give up once attempts run out.

    Returns the resulting job status ("queued" or "error").
    """
    job = session.get(Job, job_id)
    if job is None:
        return "error"
    if job.attempts >= job.max_attempts:
        job.status = "error"
        job.error_message = error
        session.commit()
        return "error"
    backoff = min(_MAX_BACKOFF_SECONDS, _BASE_BACKOFF_SECONDS * 2 ** (job.attempts - 1))
    job.status = "queued"
    job.error_message = error
    job.available_at = _now() + timedelta(seconds=backoff)
    session.commit()
    return "queued"


def recover_stuck() -> int:
    """Requeue jobs left ``running`` by a crash. Returns how many were reset.

    Attempts are not incremented here (the crash was not the job's fault); the
    next ``claim_next`` increments and the usual ``max_attempts`` guard bounds
    any job that reliably crashes the process.
    """
    with get_session_factory()() as session:
        result = cast(
            "CursorResult[Any]",
            session.execute(
                update(Job)
                .where(Job.status == "running")
                .values(status="queued", available_at=_now())
            ),
        )
        session.commit()
        return int(result.rowcount or 0)
