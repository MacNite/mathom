from fastapi.testclient import TestClient


def test_collection_crud_and_membership(client: TestClient, uploaded_mathom: dict) -> None:
    created = client.post(
        "/api/collections", json={"name": "Work Calls", "description": "Calls from work"}
    )
    assert created.status_code == 201
    collection_id = created.json()["id"]

    duplicate = client.post("/api/collections", json={"name": "Work Calls"})
    assert duplicate.status_code == 409

    added = client.post(f"/api/collections/{collection_id}/mathoms/{uploaded_mathom['id']}")
    assert added.status_code == 200
    assert len(added.json()["mathoms"]) == 1

    updated = client.put(f"/api/collections/{collection_id}", json={"name": "Calls"})
    assert updated.json()["name"] == "Calls"

    removed = client.delete(f"/api/collections/{collection_id}/mathoms/{uploaded_mathom['id']}")
    assert removed.json()["mathoms"] == []

    assert client.delete(f"/api/collections/{collection_id}").status_code == 204
    assert client.get(f"/api/collections/{collection_id}").status_code == 404
