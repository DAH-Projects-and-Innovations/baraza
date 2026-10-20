"""Démo du job de bout en bout : transcription -> draft_ready (dépôt en mémoire).

  py scripts/demo_end_to_end.py                      # faux LLM (réponse piégée)
  LLM_BASE_URL=... LLM_MODEL=... [LLM_API_KEY=...] py scripts/demo_end_to_end.py   # vrai modèle
"""
import asyncio
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm.client import LLMClient, LLMSettings  # noqa: E402
from app.llm.config import load_llm_settings  # noqa: E402
from app.minutes.generation import run_generation  # noqa: E402
from app.minutes.schema import Segment, Transcript  # noqa: E402
from app.minutes.testing import InMemoryRepository, RecordingNotifier  # noqa: E402

TRANSCRIPT = Transcript(
    meeting_id="demo-1",
    segments=[
        Segment(0, "Bonjour, on commence le point projet.", "spk_1"),
        Segment(1, "On valide le lancement de la bêta pour la fin du mois.", "spk_1"),
        Segment(2, "Bob, tu peux envoyer le rapport avant le 15 octobre ?", "spk_1"),
        Segment(3, "Oui, je m'en occupe.", "spk_2"),
    ],
    participants=["spk_1", "spk_2"],
    speaker_renames={"spk_1": "Alice", "spk_2": "Bob"},
    meeting_date=date(2026, 10, 12),
)


class FakeLLM:
    settings = LLMSettings(base_url="fake", model="fake-model")

    async def complete(self, messages, **kwargs):
        return json.dumps({
            "title": "Point projet", "summary": "Bêta validée.",
            "decisions": [{"text": "Lancer la bêta", "segment_indices": [1]}],
            "action_items": [
                {"description": "Envoyer le rapport", "owner": "Bob", "due_date": "2023-10-15", "segment_indices": [2, 3]},
                {"description": "Contacter le client", "owner": "Zoé", "due_date": None, "segment_indices": [1]},
            ],
        })


async def main():
    client = LLMClient(load_llm_settings()) if os.getenv("LLM_BASE_URL") else FakeLLM()
    repo, notifier = InMemoryRepository(TRANSCRIPT), RecordingNotifier()
    result = await run_generation("demo-1", repo=repo, client=client, notifier=notifier)

    print("Résultat du job   :", result)
    print("Statuts successifs:", " -> ".join(repo.status_history))
    print("Notifications     :", notifier.sent)
    if result.status != "draft_ready":
        print("Raison            :", repo.reason)
        return
    d = repo.drafts[0]
    print(f"Brouillon         : modèle={d.model}, prompt={d.prompt_version}")
    print(f"Titre/résumé      : {d.minutes.title} / {d.minutes.summary}")
    for dec in d.minutes.decisions:
        print(f"Décision          : {dec.text} (segments {dec.segment_indices})")
    for a in repo.action_items:
        print(f"Action créée      : {a.description} | responsable={a.owner} | échéance={a.due_date}")
    print("Corrections       :")
    for c in d.corrections:
        print(f"  - {c.kind}: {c.original_value!r} ({c.reason})")


asyncio.run(main())
