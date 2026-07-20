import io

from fastapi.testclient import TestClient


def test_upload_runs_pipeline(uploaded_mathom: dict) -> None:
    assert uploaded_mathom["status"] == "ready"
    assert uploaded_mathom["transcript"] == "This is a mocked transcript."
    assert uploaded_mathom["language"] == "en"
    assert uploaded_mathom["duration_seconds"] == 12.5
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


def test_delete_summary(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    summary_id = uploaded_mathom["summaries"][0]["id"]

    assert client.delete(f"/api/mathoms/{mathom_id}/summaries/{summary_id}").status_code == 204
    assert client.get(f"/api/mathoms/{mathom_id}").json()["summaries"] == []
    assert client.delete(f"/api/mathoms/{mathom_id}/summaries/{summary_id}").status_code == 404
