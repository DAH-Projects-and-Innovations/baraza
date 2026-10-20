"""Prompt de génération. Incrémenter PROMPT_VERSION à chaque changement."""
from __future__ import annotations

from datetime import date

from .schema import Segment

PROMPT_VERSION = "v2"

SYSTEM_PROMPT = """You write meeting minutes from a transcript.
Return ONLY a JSON object with this exact shape:
{
  "title": string,
  "summary": string,
  "decisions": [{"text": string, "segment_indices": [int]}],
  "action_items": [{"description": string, "owner": string|null,
                    "due_date": string|null, "segment_indices": [int]}]
}
Strict rules:
- Never invent a decision, an owner or a due date. If it is not explicit in the
  transcript, use null (or omit the item).
- Every decision and action item MUST cite the transcript segment numbers that
  support it in "segment_indices".
- "owner" must be a name that appears in the transcript. "due_date" must be a
  date stated in the cited segments (YYYY-MM-DD if the full date is known).
- If a date is spoken without a year, use the meeting date to infer the year
  (the next occurrence of that day and month); never use an older year.
- Write the minutes in the language of the transcript.
"""


def build_messages(
    segments: list[Segment],
    participants: list[str],
    template: str,
    meeting_date: date | None = None,
) -> list[dict]:
    lines = "\n".join(
        f"[{s.index}] {s.speaker or 'Unknown'}: {s.text}" for s in segments
    )
    user = (
        f"Meeting date: {meeting_date.isoformat() if meeting_date else 'unknown'}\n"
        f"Participants: {', '.join(participants) or 'unknown'}\n"
        f"Template / instructions:\n{template}\n\n"
        f"Transcript:\n{lines}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
