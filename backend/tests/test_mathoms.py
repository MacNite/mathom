import io

import pytest
from fastapi.testclient import TestClient


def test_upload_runs_pipeline(uploaded_mathom: dict) -> None:
    assert uploaded_mathom["status"] == "ready"
    assert uploaded_mathom["transcript"] == "This is a mocked transcript."
    assert uploaded_mathom["language"] == "en"
    assert uploaded_mathom["duration_seconds"] == 12.5
    assert uploaded_mathom["segments"] == [
        {"start": 0.0, "end": 1.0, "text": "This is a mocked transcript.", "speaker": None}
    ]
    assert len(uploaded_mathom["summaries"]) == 1
    assert uploaded_mathom["summaries"][0]["content"] == "Mocked AI reply."


def test_upload_rejects_unknown_extension(client: TestClient) -> None:
    response = client.post(
        "/api/mathoms",
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/mathoms",
        files={"file": ("empty.mp3", io.BytesIO(b""), "audio/mpeg")},
    )
    assert response.status_code == 400


def test_list_and_filters(client: TestClient, uploaded_mathom: dict) -> None:
    listed = client.get("/api/mathoms").json()
    assert len(listed) == 1

    mathom_id = uploaded_mathom["id"]
    client.patch(f"/api/mathoms/{mathom_id}", json={"favorite": True})
    assert len(client.get("/api/mathoms", params={"favorite": True}).json()) == 1
    assert len(client.get("/api/mathoms", params={"favorite": False}).json()) == 0

    client.patch(f"/api/mathoms/{mathom_id}", json={"archived": True})
    assert client.get("/api/mathoms").json() == []
    assert len(client.get("/api/mathoms", params={"archived": True}).json()) == 1


def test_update_title(client: TestClient, uploaded_mathom: dict) -> None:
    response = client.patch(f"/api/mathoms/{uploaded_mathom['id']}", json={"title": "Renamed"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


def test_tags(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    tags = client.post(f"/api/mathoms/{mathom_id}/tags", json={"name": "Ideas"}).json()
    assert [t["name"] for t in tags] == ["ideas"]

    assert len(client.get("/api/mathoms", params={"tag": "ideas"}).json()) == 1
    assert client.get("/api/tags").json()[0]["name"] == "ideas"

    remaining = client.delete(f"/api/mathoms/{mathom_id}/tags/{tags[0]['id']}").json()
    assert remaining == []


def test_audio_download(client: TestClient, uploaded_mathom: dict) -> None:
    response = client.get(f"/api/mathoms/{uploaded_mathom['id']}/audio")
    assert response.status_code == 200
    assert response.content == b"fake-audio-bytes"


def test_export_formats(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    md = client.get(f"/api/mathoms/{mathom_id}/export", params={"format": "md"})
    assert md.status_code == 200
    assert "# A test recording" in md.text
    assert "mocked transcript" in md.text

    js = client.get(f"/api/mathoms/{mathom_id}/export", params={"format": "json"})
    assert js.status_code == 200

    bad = client.get(f"/api/mathoms/{mathom_id}/export", params={"format": "pdf"})
    assert bad.status_code == 400


def test_delete_mathom(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    assert client.delete(f"/api/mathoms/{mathom_id}").status_code == 204
    assert client.get(f"/api/mathoms/{mathom_id}").status_code == 404


def test_extra_summary_with_template(client: TestClient, uploaded_mathom: dict) -> None:
    response = client.post(
        f"/api/mathoms/{uploaded_mathom['id']}/summaries",
        json={"template_slug": "tldr"},
    )
    assert response.status_code == 201
    assert response.json()["template_slug"] == "tldr"


def test_streaming_summary_chunks_long_transcripts_and_persists_content(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, uploaded_mathom: dict
) -> None:
    """Short inputs stream directly; long ones map first and stream the combine."""
    from app.config import get_settings
    from app.db import get_session_factory
    from app.models import Mathom
    from app.services import ollama

    monkeypatch.setenv("MATHOM_SUMMARY_CHUNK_CHARS", "1000")
    get_settings.cache_clear()
    streamed: list[tuple[str, str]] = []
    mapped: list[str] = []
    monkeypatch.setattr(
        ollama,
        "stream_generate_summary",
        lambda transcript, prompt, language: (
            streamed.append((transcript, prompt)) or iter(["combined"])
        ),
    )
    monkeypatch.setattr(
        ollama,
        "generate_summary",
        lambda transcript, prompt, language=None: (
            mapped.append(transcript) or f"partial:{transcript}"
        ),
    )

    mathom_id = uploaded_mathom["id"]
    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        assert mathom is not None
        mathom.transcript = "short"
        session.commit()
    short_response = client.post(f"/api/mathoms/{mathom_id}/summaries/stream", json={})
    assert short_response.status_code == 200
    assert streamed[-1][0] == "short"
    assert mapped == []

    with get_session_factory()() as session:
        mathom = session.get(Mathom, mathom_id)
        assert mathom is not None
        mathom.transcript = "a" * 2001
        session.commit()
    long_response = client.post(f"/api/mathoms/{mathom_id}/summaries/stream", json={})
    assert long_response.status_code == 200
    assert mapped == ["a" * 1000, "a" * 1000, "a"]
    assert streamed[-1][0] == "\n\n".join(f"partial:{chunk}" for chunk in mapped)

    detail = client.get(f"/api/mathoms/{mathom_id}").json()
    assert [summary["content"] for summary in detail["summaries"][-2:]] == ["combined", "combined"]


def test_streaming_summary_emits_json_parsable_tokens(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, uploaded_mathom: dict
) -> None:
    """Each SSE ``data:`` frame must be valid JSON so the browser can parse it.

    Regression guard: the stream previously emitted Python ``repr()`` (single
    quotes), which ``JSON.parse`` on the frontend rejects. Plain tokens are the
    telling case — ``repr('Hello')`` is ``'Hello'`` (invalid JSON).
    """
    import json

    from app.services import ollama

    tokens = ["Hello", " there", " friend"]
    monkeypatch.setattr(ollama, "stream_generate_summary", lambda *args, **kwargs: iter(tokens))

    mathom_id = uploaded_mathom["id"]
    response = client.post(f"/api/mathoms/{mathom_id}/summaries/stream", json={})
    assert response.status_code == 200

    decoded: list[str] = []
    for block in response.text.split("\n\n"):
        data = next((line[6:] for line in block.split("\n") if line.startswith("data: ")), None)
        if data is None or data == "done":
            continue
        decoded.append(json.loads(data))  # must not raise
    assert decoded == tokens


def test_delete_summary_purges_search_index(client: TestClient, uploaded_mathom: dict) -> None:
    """Deleting a summary must drop its text from the FTS index."""
    mathom_id = uploaded_mathom["id"]
    summary_id = uploaded_mathom["summaries"][0]["id"]
    # "reply" appears only in the mocked summary ("Mocked AI reply."), not the
    # transcript or title, so it is a clean probe for summary content.
    assert any(hit["mathom"]["id"] == mathom_id for hit in client.get("/api/search?q=reply").json())

    assert client.delete(f"/api/mathoms/{mathom_id}/summaries/{summary_id}").status_code == 204
    assert client.get("/api/search?q=reply").json() == []


def test_delete_summary(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    summary_id = uploaded_mathom["summaries"][0]["id"]

    assert client.delete(f"/api/mathoms/{mathom_id}/summaries/{summary_id}").status_code == 204
    assert client.get(f"/api/mathoms/{mathom_id}").json()["summaries"] == []
    assert client.delete(f"/api/mathoms/{mathom_id}/summaries/{summary_id}").status_code == 404


def test_edit_transcript_summary_and_subtitles(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    edited = client.patch(f"/api/mathoms/{mathom_id}", json={"transcript": "Corrected text"})
    assert edited.status_code == 200
    summary = uploaded_mathom["summaries"][0]
    changed = client.patch(
        f"/api/mathoms/{mathom_id}/summaries/{summary['id']}", json={"content": "Edited summary"}
    )
    assert changed.status_code == 200
    srt = client.get(f"/api/mathoms/{mathom_id}/export", params={"format": "srt"})
    vtt = client.get(f"/api/mathoms/{mathom_id}/export", params={"format": "vtt"})
    assert "00:00:00,000 --> 00:00:01,000" in srt.text
    assert vtt.text.startswith("WEBVTT")
