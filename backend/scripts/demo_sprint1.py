"""Démo du 19 octobre : transcription fictive -> LLM -> JSON validé -> anti-invention.

  Sans LLM (fake) :   python scripts/demo_sprint1.py
  Avec Ollama local : LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=mistral python scripts/demo_sprint1.py
"""
import asyncio
import json
from datetime import date
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.client import LLMClient  # noqa: E402
from app.llm.config import load_llm_settings  # noqa: E402
from app.minutes.anti_invention import apply_anti_invention  # noqa: E402
from app.minutes.json_output import generate_minutes_json  # noqa: E402
from app.minutes.prompts import build_messages  # noqa: E402
from app.minutes.schema import Segment  # noqa: E402

SEGMENTS = [
    Segment(0, "Bonjour à tous, on commence le point projet.", "Alice"),
    Segment(1, "On valide le lancement de la bêta pour la fin du mois.", "Alice"),
    Segment(2, "Bob, tu peux envoyer le rapport avant le 15 octobre ?", "Alice"),
    Segment(3, "Oui, je m'en occupe.", "Bob"),
]
PARTICIPANTS = ["Alice", "Bob"]
MEETING_DATE = date(2026, 10, 19)


class FakeLLM:
    async def complete(self, messages, **kwargs):
        # Réponse volontairement piégée : owner et date inventés sur la 2e action.
        return json.dumps({
            "title": "Point projet", "summary": "Lancement de la bêta validé.",
            "decisions": [{"text": "Lancer la bêta fin du mois", "segment_indices": [1]}],
            "action_items": [
                {"description": "Envoyer le rapport", "owner": "Bob",
                 "due_date": "2026-10-15", "segment_indices": [2, 3]},
                {"description": "Préparer la démo", "owner": "Zoé",
                 "due_date": "2026-11-02", "segment_indices": [1]},
            ],
        })


async def main():
    base = os.getenv("LLM_BASE_URL")
    client = (
        LLMClient(load_llm_settings()) if base else FakeLLM()
    )
    minutes = await generate_minutes_json(client, build_messages(SEGMENTS, PARTICIPANTS, "Standard", MEETING_DATE))
    cleaned, corrections = apply_anti_invention(minutes, SEGMENTS, PARTICIPANTS, MEETING_DATE)
    print(json.dumps(cleaned.model_dump(), ensure_ascii=False, indent=2))
    print("\nCorrections :")
    for c in corrections:
        print(f"- {c.kind} ({c.item_type} #{c.item_position}) : {c.original_value!r} -> {c.reason}")


asyncio.run(main())
