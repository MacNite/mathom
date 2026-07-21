"""Export a Mathom as Markdown, plain text, or JSON."""

import json
from typing import Any, cast

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


def _subtitle_timestamp(seconds: float, separator: str) -> str:
    milliseconds = round(max(seconds, 0) * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_part, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds_part:02}{separator}{milliseconds:03}"


def _subtitle_text(segment: dict[str, object]) -> str:
    speaker = str(segment.get("speaker") or "").strip()
    text = str(segment.get("text") or "").strip()
    return f"{speaker}: {text}" if speaker else text


def _subtitle_range(segment: dict[str, object], separator: str) -> str:
    start = float(cast(float | str, segment["start"]))
    end = float(cast(float | str, segment["end"]))
    return f"{_subtitle_timestamp(start, separator)} --> {_subtitle_timestamp(end, separator)}"


def to_srt(mathom: Mathom) -> str:
    """Export timestamped segments as SubRip subtitles."""
    return "\n\n".join(
        f"{index}\n{_subtitle_range(segment, ',')}\n{_subtitle_text(segment)}"
        for index, segment in enumerate(mathom.segments or [], start=1)
    ) + ("\n" if mathom.segments else "")


def to_vtt(mathom: Mathom) -> str:
    """Export timestamped segments as WebVTT subtitles."""
    cues = "\n\n".join(
        f"{_subtitle_range(segment, '.')}\n{_subtitle_text(segment)}"
        for segment in mathom.segments or []
    )
    return f"WEBVTT\n\n{cues}\n" if cues else "WEBVTT\n"
