"""Export a Mathom as Markdown, plain text, or JSON."""

import json
from typing import Any

from app.models import Mathom


def to_markdown(mathom: Mathom) -> str:
    lines = [f"# {mathom.title}", ""]
    lines.append(f"- Created: {mathom.created_at.isoformat()}")
    if mathom.duration_seconds:
        lines.append(f"- Duration: {round(mathom.duration_seconds)} s")
    if mathom.language:
        lines.append(f"- Language: {mathom.language}")
    if mathom.tags:
        lines.append(f"- Tags: {', '.join(tag.name for tag in mathom.tags)}")
    lines.append("")
    if mathom.summaries:
        for summary in mathom.summaries:
            lines += [f"## {summary.template_name}", "", summary.content, ""]
    if mathom.transcript:
        lines += ["## Transcript", "", mathom.transcript, ""]
    if mathom.chat_messages:
        lines += ["## Follow-up conversation", ""]
        for message in mathom.chat_messages:
            speaker = "You" if message.role == "user" else "Mathom"
            lines += [f"**{speaker}:** {message.content}", ""]
    return "\n".join(lines)


def to_text(mathom: Mathom) -> str:
    parts = [mathom.title, "=" * len(mathom.title), ""]
    for summary in mathom.summaries:
        parts += [summary.template_name, "-" * len(summary.template_name), summary.content, ""]
    if mathom.transcript:
        parts += ["Transcript", "----------", mathom.transcript]
    return "\n".join(parts)


def to_json(mathom: Mathom) -> str:
    data: dict[str, Any] = {
        "id": mathom.id,
        "title": mathom.title,
        "created_at": mathom.created_at.isoformat(),
        "duration_seconds": mathom.duration_seconds,
        "language": mathom.language,
        "favorite": mathom.favorite,
        "archived": mathom.archived,
        "tags": [tag.name for tag in mathom.tags],
        "transcript": mathom.transcript,
        "summaries": [
            {
                "template": summary.template_slug,
                "name": summary.template_name,
                "model": summary.model,
                "content": summary.content,
                "created_at": summary.created_at.isoformat(),
            }
            for summary in mathom.summaries
        ],
        "chat": [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }
            for message in mathom.chat_messages
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
