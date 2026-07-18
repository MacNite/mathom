from fastapi.testclient import TestClient


def test_search_finds_transcript_terms(client: TestClient, uploaded_mathom: dict) -> None:
    hits = client.get("/api/search", params={"q": "mocked transcript"}).json()
    assert len(hits) == 1
    assert hits[0]["mathom"]["id"] == uploaded_mathom["id"]
    assert "<mark>" in hits[0]["snippet"]


def test_search_prefix_matching(client: TestClient, uploaded_mathom: dict) -> None:
    hits = client.get("/api/search", params={"q": "transcr"}).json()
    assert len(hits) == 1


def test_search_no_results(client: TestClient, uploaded_mathom: dict) -> None:
    assert client.get("/api/search", params={"q": "zeppelin"}).json() == []


def test_search_handles_fts_metacharacters(client: TestClient, uploaded_mathom: dict) -> None:
    response = client.get("/api/search", params={"q": '"unbalanced OR ( NEAR'})
    assert response.status_code == 200


def test_search_after_delete(client: TestClient, uploaded_mathom: dict) -> None:
    client.delete(f"/api/mathoms/{uploaded_mathom['id']}")
    assert client.get("/api/search", params={"q": "mocked"}).json() == []


def test_timeline(client: TestClient, uploaded_mathom: dict) -> None:
    buckets = client.get("/api/timeline").json()
    assert len(buckets) == 1
    assert buckets[0]["count"] == 1
