"""A single background worker thread that drains the durable job queue.

One thread is deliberate: transcription and summarization are heavy, and the
box that runs Mathom is usually modest. Serializing the work keeps memory and
CPU predictable. The thread wakes immediately when a job is enqueued and
otherwise polls slowly.
"""

from __future__ import annotations

import logging
import threading

from app.db import get_session_factory
from app.services import jobs, pipeline

logger = logging.getLogger("mathom.worker")

# How long to sleep between polls when the queue is idle. A newly enqueued job
# wakes the thread sooner via ``notify()``.
_IDLE_POLL_SECONDS = 2.0


class Worker:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="mathom-worker", daemon=True)
        self._thread.start()
        logger.info("Job worker started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def notify(self) -> None:
        """Signal that a job was enqueued so the worker wakes promptly."""
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            worked = False
            try:
                worked = self._drain_one()
            except Exception:  # noqa: BLE001 — a bad job must never kill the worker
                logger.exception("Unexpected error in job worker loop")
            if self._stop.is_set():
                break
            if not worked:
                # Idle: wait for a nudge or the poll interval, whichever first.
                self._wake.wait(timeout=_IDLE_POLL_SECONDS)
                self._wake.clear()

    def _drain_one(self) -> bool:
        """Claim and run one job. Returns True if a job was processed."""
        with get_session_factory()() as session:
            job = jobs.claim_next(session)
            if job is None:
                return False
            job_id, mathom_id, template_slug, kind, attempts, max_attempts = (
                job.id,
                job.mathom_id,
                job.template_slug,
                job.kind,
                job.attempts,
                job.max_attempts,
            )

        try:
            if kind == "visual_analysis":
                pipeline.run_visual_analysis(mathom_id)
            else:
                pipeline.run(mathom_id, template_slug)
        except Exception as exc:  # noqa: BLE001 — decide retry vs. give up
            logger.exception("Job %s failed (attempt %s/%s)", job_id, attempts, max_attempts)
            safe = pipeline._safe_error(exc)
            with get_session_factory()() as session:
                outcome = jobs.retry_or_fail(session, job_id, safe)
            if outcome == "error":
                # Out of retries: surface the failure on the Mathom itself.
                pipeline.mark_error(mathom_id, exc)
            return True

        with get_session_factory()() as session:
            jobs.complete(session, job_id)
        return True


# Process-wide singleton; started/stopped by the app lifespan.
worker = Worker()
