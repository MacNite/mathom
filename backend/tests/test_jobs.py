"""Durable job queue: enqueue, claim, retry/backoff, and restart recovery."""

import io

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import get_session_factory
from app.models import Job, Mathom
from app.services import jobs, pipeline
from app.services.worker import Worker


def _make_mathom() -> int:
    with get_session_factory()() as session:
        mathom = Mathom(title="j", audio_path="/data/audio/j.mp3", status="pending")
        session.add(mathom)
        session.commit()
        session.refresh(mathom)
        return mathom.id


def test_enqueue_and_claim(client: TestClient) -> None:
    mathom_id = _make_mathom()
    with get_session_factory()() as session:
        jobs.enqueue(session, mathom_id, "tldr")

    with get_session_factory()() as session:
        job = jobs.claim_next(session)
        assert job is not None
        assert job.status == "running"
        assert job.attempts == 1
        assert job.template_slug == "tldr"

    # Nothing else is runnable now.
    with get_session_factory()() as session:
        assert jobs.claim_next(session) is None


def test_retry_backs_off_then_fails(client: TestClient) -> None:
    mathom_id = _make_mathom()
    with get_session_factory()() as session:
        job = jobs.enqueue(session, mathom_id, "general-summary")
        job_id = job.id

    # Attempt 1 → requeued for a later time (backoff).
    with get_session_factory()() as session:
        jobs.claim_next(session)
        assert jobs.retry_or_fail(session, job_id, "boom") == "queued"
        assert session.get(Job, job_id).available_at is not None
        # It is not immediately runnable because of the backoff delay.
        assert jobs.claim_next(session) is None

    # Force it runnable and burn the remaining attempts (max_attempts=3).
    for _ in range(2):
        with get_session_factory()() as session:
            job = session.get(Job, job_id)
            job.available_at = jobs._now()
            session.commit()
        with get_session_factory()() as session:
            claimed = jobs.claim_next(session)
            assert claimed is not None
            jobs.retry_or_fail(session, job_id, "boom")

    with get_session_factory()() as session:
        assert session.get(Job, job_id).status == "error"


def test_recover_stuck_requeues_running_jobs(client: TestClient) -> None:
    mathom_id = _make_mathom()
    with get_session_factory()() as session:
        job = jobs.enqueue(session, mathom_id, "general-summary")
        jobs.claim_next(session)  # -> running
        job_id = job.id

    assert jobs.recover_stuck() == 1
    with get_session_factory()() as session:
        assert session.get(Job, job_id).status == "queued"


def test_terminal_visual_failure_does_not_fail_ready_recording(
    client: TestClient, monkeypatch
) -> None:
    mathom_id = _make_mathom()
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        assert mathom is not None
        mathom.status = "ready"
        mathom.has_video_stream = True
        mathom.vision_status = "pending"
        job = jobs.enqueue(session, mathom_id, "general-summary", kind="visual_analysis")
        job.max_attempts = 1
        session.commit()

    monkeypatch.setattr(
        pipeline,
        "run_visual_analysis",
        lambda mathom_id: (_ for _ in ()).throw(RuntimeError("vision unavailable")),
    )
    assert Worker()._drain_one() is True

    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        job = session.get(Job, job.id)
        assert mathom is not None
        assert job is not None
        assert mathom.status == "ready"
        assert mathom.vision_status == "error"
        assert mathom.vision_error_message
        assert job.status == "error"


def test_terminal_visual_failure_reports_safe_actionable_cause(
    client: TestClient, monkeypatch
) -> None:
    mathom_id = _make_mathom()
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        assert mathom is not None
        mathom.status = "ready"
        mathom.has_video_stream = True
        job = jobs.enqueue(session, mathom_id, "general-summary", kind="visual_analysis")
        job.max_attempts = 1
        session.commit()

    from app.services import vision

    monkeypatch.setattr(
        pipeline,
        "run_visual_analysis",
        lambda mathom_id: (_ for _ in ()).throw(
            vision.VisionError("The configured local vision model is unavailable.")
        ),
    )
    assert Worker()._drain_one() is True

    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        assert mathom is not None
        assert mathom.vision_error_message == "The configured local vision model is unavailable."


def test_queue_position_follows_runnable_order(client: TestClient) -> None:
    first_id = _make_mathom()
    second_id = _make_mathom()
    with get_session_factory()() as session:
        jobs.enqueue(session, first_id, "general-summary")
        jobs.enqueue(session, second_id, "general-summary")
        assert jobs.queued_count(session) == 2
        assert jobs.queue_position(session, first_id) == 1
        assert jobs.queue_position(session, second_id) == 2


def test_upload_creates_and_finishes_a_job(client: TestClient, wait_for_status) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/mathoms",
        files={"file": ("hello.mp3", io.BytesIO(b"fake-audio-bytes"), "audio/mpeg")},
    )
    assert response.status_code == 201
    mathom_id = response.json()["id"]
    detail = wait_for_status(client, mathom_id)
    assert detail["status"] == "ready"

    # The job it created is marked done, not left dangling.
    with get_session_factory()() as session:
        job = session.query(Job).filter(Job.mathom_id == mathom_id).one()
        assert job.status == "done"


def test_upload_is_rejected_when_queue_is_full(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.services import ingest

    monkeypatch.setattr(ingest, "get_settings", lambda: Settings(max_queued_jobs=0))
    response = client.post(
        "/api/mathoms",
        files={"file": ("hello.mp3", io.BytesIO(b"audio"), "audio/mpeg")},
    )
    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"
