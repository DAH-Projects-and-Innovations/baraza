"""Tests RÉELS (issue #82 : « Test with at least Ollama and one hosted provider »).

Ignorés par défaut. Pour les activer, définir les variables puis lancer :
  pytest tests/test_live_providers.py -v -s

  Ollama :  LIVE_OLLAMA_MODEL=mistral            (URL par défaut http://localhost:11434/v1)
  Hébergé : LIVE_HOSTED_URL=https://... LIVE_HOSTED_MODEL=... LIVE_HOSTED_KEY=...
Ne JAMAIS committer de clé : passer les variables dans le terminal uniquement.
"""
import os

import pytest

from app.llm.client import LLMClient, LLMSettings
from app.minutes.json_output import generate_minutes_json
from app.minutes.prompts import build_messages
from app.minutes.schema import Segment

SEGMENTS = [
    Segment(0, "On valide le lancement de la bêta.", "Alice"),
    Segment(1, "Bob envoie le rapport avant le 15 octobre.", "Alice"),
    Segment(2, "Oui, je m'en occupe.", "Bob"),
]


def providers():
    out = []
    if os.getenv("LIVE_OLLAMA_MODEL"):
        out.append(("ollama", LLMSettings(
            base_url=os.getenv("LIVE_OLLAMA_URL", "http://localhost:11434/v1"),
            model=os.environ["LIVE_OLLAMA_MODEL"], timeout_s=180)))
    if os.getenv("LIVE_HOSTED_URL"):
        out.append(("hosted", LLMSettings(
            base_url=os.environ["LIVE_HOSTED_URL"], model=os.environ["LIVE_HOSTED_MODEL"],
            api_key=os.getenv("LIVE_HOSTED_KEY"))))
    return out


@pytest.mark.skipif(not providers(), reason="aucun fournisseur réel configuré (voir docstring)")
@pytest.mark.parametrize("name,settings", providers() or [("none", None)])
async def test_real_provider_returns_valid_minutes(name, settings):
    client = LLMClient(settings)
    minutes = await generate_minutes_json(client, build_messages(SEGMENTS, ["Alice", "Bob"], "Standard"))
    print(f"\n[{name}] format utilisé: {client.last_response_format}")
    assert minutes.summary or minutes.decisions or minutes.action_items
