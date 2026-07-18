"""Seed built-in prompt templates from prompt-templates/*.json into SQLite.

Seeding is insert-only: templates the user has edited or deleted are never
overwritten. The database copy is authoritative once seeded.
"""

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PromptTemplate

logger = logging.getLogger("mathom.seed")


def seed_templates(session: Session, templates_dir: Path | None = None) -> int:
    directory = templates_dir or get_settings().templates_dir
    if not directory.is_dir():
        logger.warning("Template seed directory %s not found; skipping seed", directory)
        return 0
    inserted = 0
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read template seed %s", path)
            continue
        slug = data.get("slug")
        prompt = data.get("prompt")
        if not slug or not prompt:
            logger.warning("Template seed %s missing slug or prompt; skipping", path)
            continue
        exists = session.execute(
            select(PromptTemplate.id).where(PromptTemplate.slug == slug)
        ).first()
        if exists:
            continue
        session.add(
            PromptTemplate(
                slug=slug,
                name=data.get("name", slug),
                description=data.get("description", ""),
                prompt=prompt,
                is_builtin=True,
            )
        )
        inserted += 1
    session.commit()
    if inserted:
        logger.info("Seeded %d prompt templates", inserted)
    return inserted
