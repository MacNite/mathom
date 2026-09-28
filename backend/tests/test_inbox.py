"""The watched folder and filename date detection."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.source_app import detect_recorded_at


@pytest.fixture()
def inbox(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    """A fresh watcher pointed at a temporary folder (the app's own watcher
    is not started because MATHOM_INBOX_DIR was unset at startup)."""
    folder = tmp_path / "inbox"
    folder.mkdir()
    monkeypatch.setenv("MATHOM_INBOX_DIR", str(folder))
    from app.config import get_settings
    from app.services.inbox import InboxWatcher

    get_settings.cache_clear()
    watcher = InboxWatcher()
    watcher.folder = folder  # type: ignore[attr-defined]
    return watcher


def _write(folder: Path, relative: str, data: bytes = b"voice") -> Path:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _mathoms(client: TestClient) -> list[dict]:
    return client.get("/api/mathoms").json()


def test_imports_settled_files_once(client: TestClient, inbox, wait_for_status) -> None:  # type: ignore[no-untyped-def]
    note = _write(inbox.folder, "WhatsApp Voice Notes/202630/PTT-20260722-WA0004.opus")
    first = inbox.scan_once()
    assert (first.imported, first.waiting) == (0, 1)  # seen once: not settled yet

    second = inbox.scan_once()
    assert second.imported == 1
    [item] = _mathoms(client)
    assert item["source_app"] == "WhatsApp"
    assert item["recorded_at"] is not None
    assert wait_for_status(client, item["id"])["status"] == "ready"

    # Unchanged on later scans; the source file is never touched.
    assert inbox.scan_once().imported == 0
    assert note.read_bytes() == b"voice"
    assert len(_mathoms(client)) == 1


def test_deleted_mathom_does_not_come_back(client: TestClient, inbox) -> None:  # type: ignore[no-untyped-def]
    _write(inbox.folder, "PTT-20260722-WA0004.opus")
    inbox.scan_once()
    inbox.scan_once()
    [item] = _mathoms(client)
    assert client.delete(f"/api/mathoms/{item['id']}").status_code == 204

    inbox.scan_once()
    inbox.scan_once()
    assert _mathoms(client) == []


def test_copies_and_touched_files_are_duplicates(client: TestClient, inbox) -> None:  # type: ignore[no-untyped-def]
    original = _write(inbox.folder, "a/PTT-20260722-WA0004.opus", b"same")
    inbox.scan_once()
    inbox.scan_once()
    _write(inbox.folder, "b/copy.opus", b"same")
    os.utime(original, (1_700_000_000, 1_700_000_000))
    inbox.scan_once()
    result = inbox.scan_once()
    assert (result.imported, result.skipped) == (0, 2)
    assert len(_mathoms(client)) == 1


def test_ignores_hidden_temp_and_foreign_files(client: TestClient, inbox) -> None:  # type: ignore[no-untyped-def]
    _write(inbox.folder, ".stfolder/marker.opus")
    _write(inbox.folder, ".syncthing.PTT-1.opus.tmp")
    _write(inbox.folder, "download.opus.part")
    _write(inbox.folder, "photo.jpg")
    _write(inbox.folder, "notes.pdf")
    (inbox.folder / "link.opus").symlink_to(Path(__file__))
    inbox.scan_once()
    result = inbox.scan_once()
    assert (result.imported, result.skipped, result.waiting) == (0, 0, 0)


def test_invalid_media_is_recorded_not_retried(client: TestClient, inbox, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.services import transcription

    def reject(path: Path) -> None:
        raise transcription.AudioValidationError("not audio")

    monkeypatch.setattr(transcription, "validate_audio", reject)
    _write(inbox.folder, "broken.opus")
    inbox.scan_once()
    assert inbox.scan_once().skipped == 1
    assert inbox.scan_once().skipped == 0  # remembered, not re-validated
    assert _mathoms(client) == []


def test_full_queue_defers_to_a_later_scan(client: TestClient, inbox, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _write(inbox.folder, "one.opus", b"1")
    inbox.scan_once()
    monkeypatch.setenv("MATHOM_MAX_QUEUED_JOBS", "0")
    from app.config import get_settings

    get_settings.cache_clear()
    deferred = inbox.scan_once()
    assert deferred.deferred and deferred.imported == 0

    monkeypatch.setenv("MATHOM_MAX_QUEUED_JOBS", "25")
    get_settings.cache_clear()
    assert inbox.scan_once().imported == 1


def test_missing_folder_is_reported(client: TestClient, inbox) -> None:  # type: ignore[no-untyped-def]
    inbox.folder.rmdir()
    inbox.scan_once()
    assert "does not exist" in inbox.last_error


def test_status_endpoint(client: TestClient, inbox) -> None:  # type: ignore[no-untyped-def]
    status = client.get("/api/ingest/inbox").json()
    assert status["enabled"] is True
    assert status["path"] == str(inbox.folder)
    # The app's own watcher was not started for this test.
    assert client.post("/api/ingest/inbox/scan").status_code == 409


def test_status_when_disabled(client: TestClient) -> None:
    assert client.get("/api/ingest/inbox").json()["enabled"] is False


@pytest.fixture()
def family(auth_harness, monkeypatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    """Two signed-in users sharing one watched folder."""
    from app.config import get_settings
    from app.services.inbox import InboxWatcher

    alice, bob = auth_harness.client(), auth_harness.client()
    auth_harness.login(alice, {"sub": "a", "email": "alice@example.com", "name": "Alice Baker"})
    auth_harness.login(bob, {"sub": "b", "email": "bob@example.com", "name": "Bob"})
    folder = tmp_path / "inbox"
    folder.mkdir()
    monkeypatch.setenv("MATHOM_INBOX_DIR", str(folder))
    get_settings.cache_clear()
    watcher = InboxWatcher()
    # The status endpoints report on the app's watcher; use this one instead.
    monkeypatch.setattr("app.routers.ingest.inbox_watcher", watcher)
    return alice, bob, folder, watcher


def test_each_user_fills_their_own_folder(family) -> None:  # type: ignore[no-untyped-def]
    alice, bob, folder, watcher = family
    assert alice.get("/api/ingest/inbox/me").json()["inbox_name"] == "alice-baker"
    assert bob.get("/api/ingest/inbox/me").json()["path"] == str(folder / "bob")

    _write(folder, "alice-baker/Voice Notes/PTT-20260722-WA0004.opus", b"hello")
    # The same forwarded note reaches both: each gets their own Mathom.
    _write(folder, "bob/PTT-20260722-WA0009.opus", b"hello")
    watcher.scan_once()
    assert watcher.scan_once().imported == 2

    [alices] = alice.get("/api/mathoms").json()
    [bobs] = bob.get("/api/mathoms").json()
    assert alices["id"] != bobs["id"]
    assert bob.get(f"/api/mathoms/{alices['id']}").status_code == 404
    assert alice.get("/api/ingest/inbox/me").json()["imported"] == 1


def test_loose_files_and_unknown_folders_are_left_alone(family) -> None:  # type: ignore[no-untyped-def]
    alice, _, folder, watcher = family
    _write(folder, "loose.opus")
    _write(folder, "carol/PTT-20260722-WA0004.opus")
    watcher.scan_once()
    assert watcher.scan_once().imported == 0

    status = alice.get("/api/ingest/inbox").json()  # Alice signed in first: admin
    assert status["per_user"] is True
    assert status["unmatched_folders"] == ["carol"]
    assert status["loose_files"] == 1
    assert {f["name"]: f["present"] for f in status["folders"]} == {
        "alice-baker": False,
        "bob": False,
    }


def test_renaming_the_folder(family) -> None:  # type: ignore[no-untyped-def]
    alice, bob, folder, watcher = family
    renamed = alice.put("/api/ingest/inbox/me", json={"inbox_name": "Alice"}).json()
    assert renamed["inbox_name"] == "alice"
    assert renamed["path"] == str(folder / "alice")

    taken = bob.put("/api/ingest/inbox/me", json={"inbox_name": "alice"})
    assert taken.status_code == 422
    for bad in ("../etc", ".hidden", "a/b", "x" * 49):
        assert bob.put("/api/ingest/inbox/me", json={"inbox_name": bad}).status_code == 422

    _write(folder, "alice/PTT-20260722-WA0004.opus")
    watcher.scan_once()
    assert watcher.scan_once().imported == 1
    assert len(alice.get("/api/mathoms").json()) == 1


def test_non_admins_cannot_see_the_admin_status(family) -> None:  # type: ignore[no-untyped-def]
    _, bob, _, _ = family
    assert bob.get("/api/ingest/inbox").status_code == 403


def test_single_user_mode_has_no_folder_names(client: TestClient, inbox) -> None:  # type: ignore[no-untyped-def]
    mine = client.get("/api/ingest/inbox/me").json()
    assert mine["per_user"] is False
    assert mine["path"] == str(inbox.folder)
    assert client.put("/api/ingest/inbox/me", json={"inbox_name": "me"}).status_code == 409


def test_slugs() -> None:
    from app.services.inbox_names import slugify

    assert slugify("Jürgen Müller-Lüdenscheidt") == "jurgen-muller-ludenscheidt"
    assert slugify("  ..Rosie!! ") == "rosie"
    assert slugify("张伟") == ""


# --- recorded_at detection ------------------------------------------------------------


def _local(*parts: int) -> datetime:
    return datetime(*parts).astimezone(UTC)  # type: ignore[arg-type]


def test_full_timestamp_in_name_wins() -> None:
    assert detect_recorded_at("audio_2026-07-22_14-03-11.ogg") == _local(2026, 7, 22, 14, 3, 11)
    assert detect_recorded_at("signal-2026-07-22-140311.m4a") == _local(2026, 7, 22, 14, 3, 11)
    assert detect_recorded_at("REC_20260722_140311.mp3") == _local(2026, 7, 22, 14, 3, 11)


def test_date_only_name_uses_mtime_on_the_same_day() -> None:
    same_day = _local(2026, 7, 22, 18, 30).timestamp()
    assert detect_recorded_at("PTT-20260722-WA0004.opus", same_day) == _local(2026, 7, 22, 18, 30)
    later = _local(2026, 9, 1, 8, 0).timestamp()
    assert detect_recorded_at("PTT-20260722-WA0004.opus", later) == _local(2026, 7, 22, 12, 0)


def test_no_date_falls_back_to_mtime_or_none() -> None:
    stamp = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    assert detect_recorded_at("memo.m4a", stamp.timestamp()) == stamp
    assert detect_recorded_at("memo.m4a") is None
    assert detect_recorded_at("PTT-20261341-WA0001.opus") is None  # not a real date
