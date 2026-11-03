"""Évaluation « zéro invention » sur les réunions d'exemple (critère d'acceptation #83)."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.minutes.evaluation import evaluate
from app.minutes.schema import Minutes, Segment

SAMPLES = sorted((Path(__file__).parent.parent / "eval_samples").glob("*.json"))


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_zero_invention_and_expected_corrections(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = [Segment(s["index"], s["text"], s.get("speaker")) for s in data["segments"]]
    md = date.fromisoformat(data["meeting_date"]) if data.get("meeting_date") else None
    res = evaluate(Minutes.model_validate(data["model_output"]), segments, data["participants"], md)
    assert res.residual_invention == 0
    assert dict(res.counts) == data["expected_corrections"]


def test_samples_exist():
    assert len(SAMPLES) >= 3
