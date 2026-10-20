"""Évaluation « zéro invention » (issue #83)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .anti_invention import apply_anti_invention
from .schema import Correction, Minutes, Segment


@dataclass
class EvalResult:
    items_before: int
    items_after: int
    corrections: list[Correction]
    counts: Counter = field(default_factory=Counter)
    residual_invention: int = 0  # doit TOUJOURS valoir 0


def evaluate(
    raw: Minutes, segments: list[Segment], participants: list[str], meeting_date: date | None = None
) -> EvalResult:
    """Applique les contrôles, puis les rejoue sur la sortie nettoyée.

    Une sortie nettoyée ne doit plus déclencher AUCUNE correction : sinon un élément
    non étayé a survécu (= invention résiduelle).
    """
    cleaned, corrections = apply_anti_invention(raw, segments, participants, meeting_date)
    _, again = apply_anti_invention(cleaned, segments, participants, meeting_date)
    return EvalResult(
        items_before=len(raw.decisions) + len(raw.action_items),
        items_after=len(cleaned.decisions) + len(cleaned.action_items),
        corrections=corrections,
        counts=Counter(c.kind for c in corrections),
        residual_invention=len(again),
    )
