"""Tag management API, multi-tag filtering, and source-origin folding."""

import io

from fastapi.testclient import TestClient


def _upload(client: TestClient, filename: str = "note.mp3") -> int:
    response = client.post(
        "/api/mathoms",
        files={"file": (filename, io.BytesIO(b"fake-audio-bytes"), "audio/mpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_recolour_and_delete_tag(client: TestClient) -> None:
    created = client.post("/api/tags", json={"name": "House", "color": "clay"})
    assert created.status_code == 201, created.text
    tag = created.json()
    assert tag["name"] == "house"
    assert tag["color"] == "clay"
    assert tag["kind"] == "manual"
    assert tag["mathom_count"] == 0

    # Duplicate names collide within one owner's vocabulary.
    assert client.post("/api/tags", json={"name": "house"}).status_code == 409

    # An unknown colour token is rejected.
    assert client.patch(f"/api/tags/{tag['id']}", json={"color": "fuchsia"}).status_code == 422

    renamed = client.patch(f"/api/tags/{tag['id']}", json={"name": "Home", "color": "moss"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "home"
    assert renamed.json()["color"] == "moss"

    assert client.delete(f"/api/tags/{tag['id']}").status_code == 204
    assert client.get("/api/tags").json() == []


def test_list_tags_reports_usage_counts(client: TestClient) -> None:
    first = _upload(client)
    second = _upload(client)
    client.post(f"/api/mathoms/{first}/tags", json={"name": "ideas"})
    client.post(f"/api/mathoms/{second}/tags", json={"name": "ideas"})
    client.post(f"/api/mathoms/{first}/tags", json={"name": "solo"})

    counts = {t["name"]: t["mathom_count"] for t in client.get("/api/tags").json()}
    assert counts == {"ideas": 2, "solo": 1}


def test_merge_tags_moves_recordings_and_removes_source(client: TestClient) -> None:
    keep = _upload(client)
    move = _upload(client)
    tags = {t["name"]: t["id"] for t in _seed_two_tags(client, keep, move)}

    merged = client.post(f"/api/tags/{tags['draft']}/merge", json={"into_id": tags["final"]})
    assert merged.status_code == 200, merged.text
    assert merged.json()["name"] == "final"
    # Both recordings now carry the surviving tag; the merged-away tag is gone.
    assert merged.json()["mathom_count"] == 2
    remaining = {t["name"] for t in client.get("/api/tags").json()}
    assert remaining == {"final"}


def _seed_two_tags(client: TestClient, keep: int, move: int) -> list[dict]:
    client.post(f"/api/mathoms/{keep}/tags", json={"name": "final"})
    client.post(f"/api/mathoms/{move}/tags", json={"name": "draft"})
    return client.get("/api/tags").json()


def test_merge_into_self_is_rejected(client: TestClient) -> None:
    tag = client.post("/api/tags", json={"name": "solo"}).json()
    resp = client.post(f"/api/tags/{tag['id']}/merge", json={"into_id": tag["id"]})
    assert resp.status_code == 400


def test_filter_by_multiple_tags_any_and_all(client: TestClient) -> None:
    both = _upload(client)
    one = _upload(client)
    for name in ("alpha", "beta"):
        client.post(f"/api/mathoms/{both}/tags", json={"name": name})
    client.post(f"/api/mathoms/{one}/tags", json={"name": "alpha"})

    # "any" (default) returns recordings carrying at least one named tag.
    any_hits = client.get("/api/mathoms", params=[("tag", "alpha"), ("tag", "beta")]).json()
    assert {m["id"] for m in any_hits} == {both, one}

    # "all" narrows to recordings carrying every named tag.
    all_hits = client.get(
        "/api/mathoms", params=[("tag", "alpha"), ("tag", "beta"), ("match", "all")]
    ).json()
    assert [m["id"] for m in all_hits] == [both]


def test_filter_untagged(client: TestClient) -> None:
    tagged = _upload(client)
    bare = _upload(client)
    client.post(f"/api/mathoms/{tagged}/tags", json={"name": "kept"})

    untagged = client.get("/api/mathoms", params={"untagged": True}).json()
    assert [m["id"] for m in untagged] == [bare]


def test_source_app_is_folded_into_a_managed_tag(client: TestClient) -> None:
    mathom_id = _upload(client, "PTT-20260722-WA0004.mp3")

    # The recording carries an auto-applied source tag alongside its source_app.
    detail = client.get(f"/api/mathoms/{mathom_id}").json()
    assert detail["source_app"] == "WhatsApp"
    source_tags = [t for t in detail["tags"] if t["kind"] == "source"]
    assert [t["name"] for t in source_tags] == ["whatsapp"]

    # It appears in the shared vocabulary and filters like any other tag.
    listed = {t["name"]: t for t in client.get("/api/tags").json()}
    assert listed["whatsapp"]["kind"] == "source"
    hits = client.get("/api/mathoms", params={"tag": "whatsapp"}).json()
    assert [m["id"] for m in hits] == [mathom_id]


def test_source_tag_cannot_be_renamed(client: TestClient) -> None:
    _upload(client, "PTT-20260722-WA0004.mp3")
    source = next(t for t in client.get("/api/tags").json() if t["kind"] == "source")
    resp = client.patch(f"/api/tags/{source['id']}", json={"name": "whatever"})
    assert resp.status_code == 400
    # Recolouring a source tag is still allowed.
    assert client.patch(f"/api/tags/{source['id']}", json={"color": "teal"}).status_code == 200
