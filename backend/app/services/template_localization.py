"""Localized built-in prompt templates.

Built-in templates are kept in their English database form so existing edits
remain authoritative.  Their optional translations live next to the seed files
and are used only while the database copy still matches the shipped English
prompt.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models import PromptTemplate

SUPPORTED_TEMPLATE_LANGUAGES = frozenset({"en", "de", "es"})


@lru_cache(maxsize=4)
def _seed_data(directory: str) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    for path in Path(directory).glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data.get("slug"), str):
            templates[data["slug"]] = data
    return templates


def normalize_template_language(language: str | None) -> str:
    """Return a supported UI language, falling back safely to English."""
    code = (language or "en").strip().lower()
    return code if code in SUPPORTED_TEMPLATE_LANGUAGES else "en"


def localized_template(template: PromptTemplate, language: str | None) -> dict[str, Any]:
    """Return template fields translated for a selected UI language when safe.

    A user-edited built-in template is deliberately not replaced with a shipped
    translation: the edit remains the source of truth.
    """
    result = {
        "id": template.id,
        "slug": template.slug,
        "name": template.name,
        "description": template.description,
        "prompt": template.prompt,
        "is_builtin": template.is_builtin,
        "updated_at": template.updated_at,
    }
    if not template.is_builtin:
        return result

    source = _seed_data(str(get_settings().templates_dir)).get(template.slug, {})
    if template.prompt != source.get("prompt"):
        return result
    translation = source.get("translations", {}).get(normalize_template_language(language), {})
    if not isinstance(translation, dict):
        return result
    for field in ("name", "description", "prompt"):
        value = translation.get(field)
        if isinstance(value, str):
            result[field] = value
    return result


def localized_prompt(template: PromptTemplate, language: str | None) -> str:
    """Get the prompt text that should be sent to the LLM."""
    return str(localized_template(template, language)["prompt"])
