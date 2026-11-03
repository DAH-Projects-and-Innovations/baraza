"""Évaluation « zéro invention » (issue #83).

Usage :
  py scripts/eval_invention.py [dossier] [--show] [--live]

  (sans option)  sorties de modèle ENREGISTRÉES dans les fichiers ("model_output") : aucun LLM.
  --live         appelle le VRAI modèle sur chaque réunion (ignore "model_output").
                 Variables : LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (si besoin), LLM_TIMEOUT_S (ex. 180 pour Ollama).
  --show         affiche la transcription et le compte rendu généré (lisible), pas seulement les compteurs.

Exemples :
  py scripts/eval_invention.py                          # démo rapide, sans modèle
  py scripts/eval_invention.py eval_samples --live --show

Format d'un fichier : {name, meeting_date?, participants, segments[{index,speaker,text}],
                       model_output?, expected_corrections?}
Pour utiliser les réunions fictives de eval/, adapter seulement load_meeting().
"""
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.minutes.evaluation import evaluate  # noqa: E402
from app.minutes.schema import Minutes, Segment  # noqa: E402


def load_meeting(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = [Segment(index=s["index"], text=s["text"], speaker=s.get("speaker")) for s in data["segments"]]
    meeting_date = date.fromisoformat(data["meeting_date"]) if data.get("meeting_date") else None
    return data, segments, meeting_date


async def get_minutes(data, segments, meeting_date=None, live=False):
    if "model_output" in data and not live:
        return Minutes.model_validate(data["model_output"])
    from app.llm.client import LLMClient
    from app.llm.config import load_llm_settings
    from app.minutes.json_output import generate_minutes_json
    from app.minutes.prompts import build_messages

    for var in ("LLM_BASE_URL", "LLM_MODEL"):
        if not os.getenv(var):
            sys.exit(f"Variable {var} non définie dans cette fenêtre (voir l'aide en tête du script).")
    client = LLMClient(load_llm_settings())  # lit aussi LLM_TIMEOUT_S, LLM_MAX_OUTPUT_TOKENS...
    return await generate_minutes_json(client, build_messages(segments, data["participants"], "Standard", meeting_date))


def show(segments, minutes):
    print("   --- Transcription")
    for s in segments:
        print(f"   [{s.index}] {s.speaker or '?'}: {s.text}")
    print("   --- Compte rendu généré par le modèle")
    print(f"   Titre  : {minutes.title}")
    print(f"   Résumé : {minutes.summary}")
    for d in minutes.decisions:
        print(f"   Décision : {d.text}  (segments {d.segment_indices})")
    for a in minutes.action_items:
        print(f"   Action   : {a.description}  | responsable={a.owner} | échéance={a.due_date}"
              f"  (segments {a.segment_indices})")
    print("   --- Contrôles")


async def main(folder: str, live: bool, display: bool) -> int:
    failures, total = 0, Counter()
    files = sorted(Path(folder).glob("*.json"))
    if not files:
        print(f"Aucun fichier .json dans {folder}")
        return 1
    for path in files:
        data, segments, meeting_date = load_meeting(path)
        minutes = await get_minutes(data, segments, meeting_date, live)
        res = evaluate(minutes, segments, data["participants"], meeting_date)
        total.update(res.counts)
        print(f"\n== {data['name']} ({path.name})")
        if display:
            show(segments, minutes)
        print(f"   éléments : {res.items_before} avant -> {res.items_after} après")
        for c in res.corrections:
            print(f"   - {c.kind:22} {c.item_type} #{c.item_position}: {c.original_value!r}")
        print(f"   invention résiduelle : {res.residual_invention}")
        if res.residual_invention:
            failures += 1
        expected = data.get("expected_corrections")
        if not live and expected is not None and dict(res.counts) != expected:
            print(f"   ECART : attendu {expected}, obtenu {dict(res.counts)}")
            failures += 1
    print(f"\nTotal corrections : {dict(total)}")
    print("RÉSULTAT :", "ÉCHEC" if failures else "OK, zéro invention résiduelle")
    return 1 if failures else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    sys.exit(asyncio.run(main(args[0] if args else "eval_samples", "--live" in flags, "--show" in flags)))
