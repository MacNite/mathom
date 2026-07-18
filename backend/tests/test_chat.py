import httpx
import pytest
from fastapi.testclient import TestClient


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


def test_chat_translates_missing_model_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama replies 404 when the model was never pulled — surface it clearly."""
    from app.services import ollama

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'llama3.2' not found"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        ollama,
        "_client",
        lambda: httpx.Client(transport=transport, base_url="http://ollama:11434"),
    )

    with pytest.raises(ollama.OllamaModelNotFoundError) as excinfo:
        ollama.chat([{"role": "user", "content": "hi"}])
    message = str(excinfo.value)
    assert "llama3.2" in message
    assert "make models" in message


def test_chat_endpoint_reports_missing_model(
    client: TestClient, uploaded_mathom: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import ollama

    def boom(*args: object, **kwargs: object) -> str:
        raise ollama.OllamaModelNotFoundError("llama3.2")

    monkeypatch.setattr(ollama, "followup_chat", boom)

    response = client.post(
        f"/api/mathoms/{uploaded_mathom['id']}/chat", json={"message": "hi"}
    )
    assert response.status_code == 503
    assert "llama3.2" in response.json()["detail"]
