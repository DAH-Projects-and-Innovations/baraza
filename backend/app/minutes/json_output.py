"""Sorties JSON robustes quel que soit le modèle (issue #82)."""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.llm.errors import InvalidModelOutputError

from .schema import Minutes, minutes_json_schema


def extract_json(text: str) -> dict:
    """Tolère ```json ...```, texte avant/après l'objet JSON."""
    t = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fenced:
        t = fenced.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(t[start : end + 1])


def describe_error(exc: Exception, limit: int = 5) -> str:
    """Résumé de l'erreur pour le prompt de réparation.

    Chemins et messages uniquement : jamais les valeurs reçues (pas de fuite de contenu).
    """
    if isinstance(exc, ValidationError):
        parts = [
            f"{'.'.join(str(x) for x in e['loc']) or 'root'}: {e['msg']}"
            for e in exc.errors()[:limit]
        ]
        return "schema errors -> " + "; ".join(parts)
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})"
    return str(exc)


async def generate_minutes_json(
    client, messages: list[dict], *, max_repairs: int = 1
) -> Minutes:
    """Appelle le LLM, valide avec Pydantic, puis tente UNE réparation (max_repairs=1).

    Le client choisit json_schema / json_object / aucun selon ce que le fournisseur accepte.
    """
    schema = minutes_json_schema()
    msgs = list(messages)
    for attempt in range(max_repairs + 1):
        raw = await client.complete(msgs, json_mode=True, json_schema=schema)
        try:
            return Minutes.model_validate(extract_json(raw))
        except (ValueError, ValidationError) as exc:  # JSONDecodeError ⊂ ValueError
            summary = describe_error(exc)
            if attempt == max_repairs:
                raise InvalidModelOutputError(summary) from exc
            msgs = msgs + [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        f"Your previous answer was invalid: {summary}. "
                        "Return ONLY the corrected JSON object matching the required "
                        "schema, with no other text."
                    ),
                },
            ]
    raise InvalidModelOutputError()  # pragma: no cover
