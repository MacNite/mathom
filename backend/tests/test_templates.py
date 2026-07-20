from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.models import Mathom
from app.services import ollama, pipeline

EXPECTED_SEEDS = {
    "general-summary",
    "tldr",
    "meeting-minutes",
    "action-items",
    "customer-call",
    "technical-discussion",
    "email-draft",
    "github-issue",
    "jira-issue",
    "crm-entry",
    "calendar-events",
    "executive-brief",
}


def test_seeded_templates_present(client: TestClient) -> None:
    response = client.get("/api/templates")
    assert response.status_code == 200
    slugs = {t["slug"] for t in response.json()}
    assert slugs >= EXPECTED_SEEDS
    assert all(t["is_builtin"] for t in response.json() if t["slug"] in EXPECTED_SEEDS)


def test_create_update_delete_template(client: TestClient) -> None:
    created = client.post(
        "/api/templates",
        json={
            "slug": "my-notes",
            "name": "My Notes",
            "description": "Personal note style",
            "prompt": "Rewrite as notes: {transcript}",
        },
    )
    assert created.status_code == 201
    template_id = created.json()["id"]

    updated = client.put(f"/api/templates/{template_id}", json={"name": "My Better Notes"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "My Better Notes"

    deleted = client.delete(f"/api/templates/{template_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/templates/{template_id}").status_code == 404


def test_prompt_must_contain_transcript_placeholder(client: TestClient) -> None:
    response = client.post(
        "/api/templates",
        json={"slug": "broken", "name": "Broken", "prompt": "No placeholder here"},
    )
    assert response.status_code == 422


def test_duplicate_slug_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/templates",
        json={"slug": "tldr", "name": "Dup", "prompt": "x {transcript}"},
    )
    assert response.status_code == 409


def test_builtin_template_is_localized_for_selected_language(client: TestClient) -> None:
    templates = client.get("/api/templates?language=de").json()
    template = next(item for item in templates if item["slug"] == "general-summary")
    assert template["name"] == "Allgemeine Zusammenfassung"
    assert "Fasse das folgende Transkript" in template["prompt"]
    assert "{transcript}" in template["prompt"]


def test_unsupported_template_language_falls_back_to_english(client: TestClient) -> None:
    templates = client.get("/api/templates?language=fr").json()
    template = next(item for item in templates if item["slug"] == "general-summary")
    assert template["prompt"].startswith("Summarize the following transcript")


def test_summary_uses_the_selected_language_prompt(
    client: TestClient, monkeypatch, uploaded_mathom: dict
) -> None:
    captured: dict[str, str] = {}

    def capture_prompt(transcript: str, prompt: str, language: str | None = None) -> str:
        captured["prompt"] = prompt
        return "Zusammenfassung"

    monkeypatch.setattr(ollama, "generate_summary", capture_prompt)
    summary = pipeline.summarize_mathom(uploaded_mathom["id"], "tldr", "de")

    assert summary is not None
    assert captured["prompt"].startswith("Gib eine Kurzfassung")
    assert captured["prompt"].endswith("Transkript:\n{transcript}")
    with get_session_factory()() as session:
        mathom = session.get(Mathom, uploaded_mathom["id"])
        assert mathom is not None
