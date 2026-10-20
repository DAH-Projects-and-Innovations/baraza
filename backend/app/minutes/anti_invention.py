"""Contrôles anti-invention (issue #83). Fonction pure, sans I/O.

Règle dure : on n'invente jamais une décision, un responsable ou une échéance.
Principe : en cas de doute, on met à null (ou on rejette) et on le trace.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from .schema import ActionItem, Correction, Decision, Minutes, Segment

_FR_MONTHS = "janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre".split("|")
_EN_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december".split("|")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def _word_in(needle: str, haystack: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack))


def owner_is_supported(owner: str, cited_text: str, participants: list[str]) -> bool:
    o = normalize(owner)
    if not o:
        return False
    if _word_in(o, cited_text):
        return True
    o_tokens = set(o.split())
    for p in participants:
        p_tokens = set(normalize(p).split())
        if p_tokens and (o_tokens <= p_tokens or p_tokens <= o_tokens):
            return True  # "Thierry" ↔ "Thierry Martin"
    return False


_MONTHS_ALL = "|".join(_FR_MONTHS + _EN_MONTHS)
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[t ].*)?")
_DMY = re.compile(r"(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{4}|\d{2}))?")
_DAY_MONTH_NAME = re.compile(
    rf"(\d{{1,2}})(?:er|st|nd|rd|th)?\s+(?:de\s+|of\s+)?({_MONTHS_ALL})(?:\s+(\d{{4}}))?"
)
_MONTH_NAME_DAY = re.compile(rf"({_MONTHS_ALL})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?")
_YEAR_IN_TEXT = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")


def _month_number(name: str) -> int:
    return (_FR_MONTHS.index(name) if name in _FR_MONTHS else _EN_MONTHS.index(name)) + 1


def _year(raw: str | None) -> int | None:
    if raw is None:
        return None
    return 2000 + int(raw) if len(raw) == 2 else int(raw)


def _parse_date(due: str) -> tuple[int, int, int | None] | None:
    """Extrait (jour, mois, année ou None) d'une échéance ISO, jj/mm[/aaaa] ou en toutes lettres.

    jj/mm est lu jour d'abord (convention française).
    """
    d = normalize(due)
    if m := _ISO.fullmatch(d):
        day, month, year = int(m.group(3)), int(m.group(2)), int(m.group(1))
    elif m := _DMY.fullmatch(d):
        day, month, year = int(m.group(1)), int(m.group(2)), _year(m.group(3))
    elif m := _DAY_MONTH_NAME.fullmatch(d):
        day, month, year = int(m.group(1)), _month_number(m.group(2)), _year(m.group(3))
    elif m := _MONTH_NAME_DAY.fullmatch(d):
        day, month, year = int(m.group(2)), _month_number(m.group(1)), _year(m.group(3))
    else:
        return None
    return (day, month, year) if 1 <= month <= 12 and 1 <= day <= 31 else None


def due_date_is_supported(due: str, cited_text: str) -> bool:
    """True si jour et mois de l'échéance sont retrouvables dans le texte cité (normalisé).

    L'année est vérifiée séparément (voir _year_check).
    """
    if not due or not due.strip():
        return False
    if _word_in(normalize(due), cited_text):  # texte identique ("vendredi", "2026-10-15")
        return True
    parsed = _parse_date(due)
    if parsed is None:  # texte libre introuvable
        return False
    day, month, _ = parsed
    names = f"{_FR_MONTHS[month - 1]}|{_EN_MONTHS[month - 1]}"
    patterns = [
        rf"(?<!\d)0?{day}\s*[/.\-]\s*0?{month}(?!\d)",  # 15/10, 15-10, 15.10
        rf"(?<!\d)0?{day}(?:er|st|nd|rd|th)?\s+(?:de\s+|of\s+)?(?:{names})\b",
        rf"\b(?:{names})\s+0?{day}(?:st|nd|rd|th)?(?!\d)",
    ]
    return any(re.search(p, cited_text) for p in patterns)


def _resolve_year(day: int, month: int, meeting_date: date) -> int:
    """Année de la prochaine occurrence de (jour, mois) à partir de la date de réunion."""
    try:
        candidate = date(meeting_date.year, month, day)
    except ValueError:
        return meeting_date.year
    return meeting_date.year if candidate >= meeting_date else meeting_date.year + 1


def _year_check(due: str, cited_text: str, meeting_date: date):
    """None si l'année est acceptable, sinon (nouvelle_valeur|None, kind, raison).

    - Année écrite dans le texte cité : celle de la date doit en faire partie, sinon null.
    - Année non écrite : l'année est déduite de la date de réunion ; si le modèle en a
      mis une autre (ex. 2023), elle est corrigée et la correction est tracée.
    """
    parsed = _parse_date(due)
    if parsed is None or parsed[2] is None:
        return None
    day, month, year = parsed
    stated = {int(y) for y in _YEAR_IN_TEXT.findall(cited_text)}
    if stated:
        if year in stated:
            return None
        return (None, "due_date_nulled", "année absente des segments cités")
    expected = _resolve_year(day, month, meeting_date)
    if year == expected:
        return None
    return (
        f"{expected:04d}-{month:02d}-{day:02d}",
        "due_date_year_adjusted",
        f"année non citée : déduite de la date de réunion ({meeting_date.isoformat()})",
    )


def _cited(indices: list[int], by_index: dict[int, Segment]) -> str:
    parts = []
    for i in indices:
        seg = by_index[i]
        parts.append(f"{seg.speaker or ''} {seg.text}")
    return normalize(" ".join(parts))


def _valid_indices(indices: list[int], by_index: dict[int, Segment]) -> bool:
    return bool(indices) and all(i in by_index for i in indices)


def apply_anti_invention(
    minutes: Minutes,
    segments: list[Segment],
    participants: list[str],
    meeting_date: date | None = None,
) -> tuple[Minutes, list[Correction]]:
    by_index = {s.index: s for s in segments}
    corrections: list[Correction] = []

    decisions: list[Decision] = []
    for pos, d in enumerate(minutes.decisions):
        if not _valid_indices(d.segment_indices, by_index):
            corrections.append(Correction(
                kind="item_rejected", item_type="decision", item_position=pos,
                original_value=d.text,
                reason="segment_indices vides ou hors limites",
            ))
            continue
        decisions.append(d)

    actions: list[ActionItem] = []
    for pos, a in enumerate(minutes.action_items):
        if not _valid_indices(a.segment_indices, by_index):
            corrections.append(Correction(
                kind="item_rejected", item_type="action_item", item_position=pos,
                original_value=a.description,
                reason="segment_indices vides ou hors limites",
            ))
            continue
        text = _cited(a.segment_indices, by_index)
        owner, due = a.owner, a.due_date
        if owner and not owner_is_supported(owner, text, participants):
            corrections.append(Correction(
                kind="owner_nulled", item_type="action_item", item_position=pos,
                original_value=owner,
                reason="nom absent des segments cités et des participants",
            ))
            owner = None
        if due and not due_date_is_supported(due, text):
            corrections.append(Correction(
                kind="due_date_nulled", item_type="action_item", item_position=pos,
                original_value=due,
                reason="échéance introuvable dans les segments cités",
            ))
            due = None
        elif due and meeting_date is not None:
            fix = _year_check(due, text, meeting_date)
            if fix is not None:
                new_due, kind, reason = fix
                corrections.append(Correction(
                    kind=kind, item_type="action_item", item_position=pos,
                    original_value=due, reason=reason,
                ))
                due = new_due
        actions.append(a.model_copy(update={"owner": owner, "due_date": due}))

    cleaned = minutes.model_copy(update={"decisions": decisions, "action_items": actions})
    return cleaned, corrections
