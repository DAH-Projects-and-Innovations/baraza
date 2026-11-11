"""Minutes contrôlées (#81 à #89) : sortie JSON robuste, une réparation, anti-invention.

Indépendant du stockage : le worker lit la transcription du dossier de réunion et y écrit
les minutes nettoyées et la trace des corrections.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from pydantic import ValidationError

from baraza.core.anti_invention import Correction, apply_anti_invention
from baraza.core.generation import load_prompt, render_transcript
from baraza.core.minutes import Minutes
from baraza.llm.errors import InvalidModelOutputError

SUPPORTED_LANGUAGES = ("fr", "en")


# ---------------- sortie JSON robuste (#82) ----------------


def extract_json(text: str) -> dict[str, Any]:
    """Tolère les balises ```json et le texte autour de l'objet JSON."""
    t = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fenced:
        t = fenced.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    parsed: dict[str, Any] = json.loads(t[start : end + 1])
    return parsed


def describe_error(exc: Exception, limit: int = 5) -> str:
    """Chemins et messages seulement : jamais les valeurs reçues (pas de fuite de contenu)."""
    if isinstance(exc, ValidationError):
        parts = [
            f"{'.'.join(str(x) for x in e['loc']) or 'root'}: {e['msg']}"
            for e in exc.errors()[:limit]
        ]
        return "schema errors -> " + "; ".join(parts)
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})"
    return str(exc)


def normalize_language(language: str | None) -> str:
    code = (language or "").strip().lower()[:2]
    return code if code in SUPPORTED_LANGUAGES else "en"


def prompt_version_of(system_prompt: str, language: str) -> str:
    """Version automatique : change dès que le fichier de prompt change."""
    return f"{language}-{hashlib.sha256(system_prompt.encode('utf-8')).hexdigest()[:8]}"


async def generate_checked_minutes(
    transcript: Any,
    llm: Any,
    *,
    meeting_date: date | None = None,
    max_repairs: int = 1,
) -> tuple[Minutes, list[Correction], str]:
    """Retourne (minutes nettoyées, corrections, version du prompt).

    ``transcript`` : tout objet avec .segments (speaker, start, text) et .language.
    Une seule réparation : le message d'erreur de validation est renvoyé au modèle.
    """
    language = normalize_language(getattr(transcript, "language", None))
    system = load_prompt("minutes", language)
    user = render_transcript(transcript)
    if meeting_date is not None:
        user = (
            f"Meeting date: {meeting_date.isoformat()} (if a date is spoken without a year, "
            f"infer the year from this date)\n{user}"
        )
    schema = Minutes.model_json_schema()

    attempt_user = user
    for attempt in range(max_repairs + 1):
        raw = await llm.complete_json(system, attempt_user, schema=schema)
        try:
            minutes = Minutes.model_validate(extract_json(raw))
            break
        except (ValueError, ValidationError) as exc:  # JSONDecodeError est un ValueError
            summary = describe_error(exc)
            if attempt == max_repairs:
                raise InvalidModelOutputError(summary) from exc
            attempt_user = (
                f"{user}\n\nYour previous answer was invalid: {summary}. "
                "Return ONLY the corrected JSON object matching the required schema."
            )
    cleaned, corrections = apply_anti_invention(minutes, transcript.segments, meeting_date)
    return cleaned, corrections, prompt_version_of(system, language)
