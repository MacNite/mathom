from fastapi.testclient import TestClient

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
