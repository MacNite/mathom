from fastapi.testclient import TestClient

from app.routers import chat


def test_chat_roundtrip(client: TestClient, uploaded_mathom: dict) -> None:
    mathom_id = uploaded_mathom["id"]
    response = client.post(
        f"/api/mathoms/{mathom_id}/chat", json={"message": "What was this about?"}
    )
    assert response.status_code == 200
    messages = response.json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Mocked AI reply."

    listed = client.get(f"/api/mathoms/{mathom_id}/chat").json()
    assert len(listed) == 2

    assert client.delete(f"/api/mathoms/{mathom_id}/chat").status_code == 204
    assert client.get(f"/api/mathoms/{mathom_id}/chat").json() == []


def test_chat_requires_transcript(client: TestClient) -> None:
    response = client.post("/api/mathoms/999/chat", json={"message": "hi"})
    assert response.status_code == 404


def test_chat_returns_busy_when_interactive_slot_is_taken(
    client: TestClient, uploaded_mathom: dict
) -> None:
    assert chat._try_acquire_chat_slot()
    try:
        response = client.post(f"/api/mathoms/{uploaded_mathom['id']}/chat", json={"message": "hi"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "5"
    finally:
        assert chat._chat_slots is not None
        chat._chat_slots.release()
