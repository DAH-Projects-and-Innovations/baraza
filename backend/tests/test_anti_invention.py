from app.minutes.anti_invention import apply_anti_invention
from app.minutes.schema import ActionItem, Decision, Minutes, Segment

SEGS = [
    Segment(0, "On valide le budget de 5000 euros.", "Alice"),
    Segment(1, "Bob enverra le rapport avant le 15 octobre.", "Alice"),
    Segment(2, "D'accord, je m'en occupe.", "Bob"),
    Segment(3, "Je ferai la revue d'ici vendredi.", "Chloé"),
]
PARTICIPANTS = ["Alice", "Bob Martin", "Chloé"]


def run(*actions, decisions=()):
    m = Minutes(decisions=list(decisions), action_items=list(actions))
    return apply_anti_invention(m, SEGS, PARTICIPANTS)


def test_valid_item_untouched():
    out, corr = run(ActionItem(description="Rapport", owner="Bob", due_date="2026-10-15", segment_indices=[1, 2]))
    assert corr == []
    assert out.action_items[0].owner == "Bob" and out.action_items[0].due_date == "2026-10-15"


def test_invented_owner_is_nulled():
    out, corr = run(ActionItem(description="Rapport", owner="Zoé", segment_indices=[1]))
    assert out.action_items[0].owner is None
    assert [c.kind for c in corr] == ["owner_nulled"] and corr[0].original_value == "Zoé"


def test_owner_in_participants_but_not_in_segment_is_kept():
    out, _ = run(ActionItem(description="x", owner="Bob Martin", segment_indices=[0]))
    assert out.action_items[0].owner == "Bob Martin"


def test_owner_accents_and_case_insensitive():
    out, corr = run(ActionItem(description="x", owner="CHLOE", segment_indices=[3]))
    assert out.action_items[0].owner == "CHLOE" and corr == []


def test_invented_date_is_nulled():
    out, corr = run(ActionItem(description="x", due_date="2026-11-30", segment_indices=[1]))
    assert out.action_items[0].due_date is None
    assert corr[0].kind == "due_date_nulled"


def test_date_with_wrong_month_is_nulled():
    out, _ = run(ActionItem(description="x", due_date="2026-11-15", segment_indices=[1]))
    assert out.action_items[0].due_date is None  # "15 octobre" ≠ novembre


def test_free_text_date_found_in_segment():
    out, corr = run(ActionItem(description="x", due_date="vendredi", segment_indices=[3]))
    assert out.action_items[0].due_date == "vendredi" and corr == []


def test_empty_or_out_of_range_indices_rejected():
    out, corr = run(
        ActionItem(description="a", segment_indices=[]),
        ActionItem(description="b", segment_indices=[99]),
        decisions=[Decision(text="d", segment_indices=[42])],
    )
    assert out.action_items == [] and out.decisions == []
    assert len(corr) == 3


def test_decision_kept_when_cited():
    out, corr = run(decisions=[Decision(text="Budget validé", segment_indices=[0])])
    assert len(out.decisions) == 1 and corr == []


# ---------------- formats de date écrits par le modèle ----------------
import pytest

from app.minutes.anti_invention import due_date_is_supported, normalize, owner_is_supported


def sup(due, text):
    return due_date_is_supported(due, normalize(text))


@pytest.mark.parametrize("due,text", [
    ("2026-10-15", "avant le 15 octobre"),
    ("2026-10-15", "avant le 15/10"),
    ("2026-10-15", "avant le 15-10"),
    ("2026-10-15", "avant le 15 octobre 2026"),
    ("2026-10-01", "pour le 1er octobre"),
    ("2026-10-15", "by October 15th"),
    ("2026-10-15", "by the 15th of October"),
    ("15/10/2026", "avant le 15 octobre"),
    ("15 octobre 2026", "avant le 15/10"),
    ("October 15, 2026", "avant le 15 octobre"),
    ("2026-10-15T00:00:00", "avant le 15 octobre"),
    ("vendredi", "On se voit vendredi."),
    ("next friday", "I'll do it next Friday."),
])
def test_dates_found_in_cited_text(due, text):
    assert sup(due, text)


@pytest.mark.parametrize("due,text", [
    ("2026-11-15", "avant le 15 octobre"),      # mauvais mois
    ("2026-10-16", "avant le 15 octobre"),      # mauvais jour
    ("2026-10-05", "avant le 15 octobre"),      # 5 ≠ 15
    ("2026-10-15", "on valide le budget de 115/10 euros"),  # nombre voisin
    ("2026-10-15", "à la fin du mois"),
    ("vendredi", "on se voit lundi"),
    ("", "avant le 15 octobre"),
    ("n'importe quoi", "avant le 15 octobre"),
])
def test_dates_not_found_are_unsupported(due, text):
    assert not sup(due, text)


def test_owner_with_extra_spaces_and_case():
    assert owner_is_supported("  ALICE ", normalize("alice parle"), [])


def test_owner_not_found_anywhere():
    assert not owner_is_supported("Zoé", normalize("Alice dit bonjour"), ["Alice", "Bob"])


def test_original_values_are_recorded_for_reviewers():
    out, corr = run(ActionItem(description="x", owner="Zoé", due_date="2026-11-30", segment_indices=[1]))
    assert {c.kind: c.original_value for c in corr} == {"owner_nulled": "Zoé", "due_date_nulled": "2026-11-30"}
    assert all(c.reason for c in corr)


def test_input_is_not_mutated():
    m = Minutes(action_items=[ActionItem(description="x", owner="Zoé", segment_indices=[1])])
    apply_anti_invention(m, SEGS, PARTICIPANTS)
    assert m.action_items[0].owner == "Zoé"


def test_rejected_count_exact():
    _, corr = run(
        ActionItem(description="a", segment_indices=[]),
        ActionItem(description="b", segment_indices=[99]),
        decisions=[Decision(text="d", segment_indices=[42])],
    )
    assert [c.kind for c in corr] == ["item_rejected"] * 3


# ---------------- année des échéances (cas réel : le modèle a écrit 2023) ----------------
from datetime import date

MEETING = date(2026, 10, 12)
YEARLESS = [Segment(0, "Bob, tu peux envoyer le rapport avant le 15 octobre ?", "Alice"),
            Segment(1, "Le contrat expire le 5 mars 2025.", "Alice"),
            Segment(2, "On se voit avant le 5 mars.", "Alice")]


def run_year(due, idx, meeting=MEETING):
    m = Minutes(action_items=[ActionItem(description="x", due_date=due, segment_indices=[idx])])
    out, corr = apply_anti_invention(m, YEARLESS, ["Alice", "Bob"], meeting)
    return out.action_items[0].due_date, corr


def test_invented_year_is_replaced_by_meeting_year_and_recorded():
    due, corr = run_year("2023-10-15", 0)
    assert due == "2026-10-15"
    assert [(c.kind, c.original_value) for c in corr] == [("due_date_year_adjusted", "2023-10-15")]


def test_correct_year_is_left_untouched():
    due, corr = run_year("2026-10-15", 0)
    assert due == "2026-10-15" and corr == []


def test_date_already_past_this_year_means_next_year():
    due, corr = run_year("2026-03-05", 2)          # dit en octobre 2026 : "avant le 5 mars"
    assert due == "2027-03-05" and corr[0].kind == "due_date_year_adjusted"


def test_year_stated_in_text_must_match():
    assert run_year("2025-03-05", 1)[0] == "2025-03-05"    # "5 mars 2025" cité
    due, corr = run_year("2026-03-05", 1)                   # autre année que celle citée
    assert due is None and corr[0].kind == "due_date_nulled"


def test_no_meeting_date_means_year_is_not_checked():
    due, corr = run_year("2023-10-15", 0, meeting=None)
    assert due == "2023-10-15" and corr == []      # limite documentée


def test_date_without_year_is_untouched():
    due, corr = run_year("15 octobre", 0)
    assert due == "15 octobre" and corr == []
