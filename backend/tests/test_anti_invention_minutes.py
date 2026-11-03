from datetime import date

import pytest

from baraza.core.anti_invention import (
    apply_anti_invention, due_date_is_supported, normalize, owner_is_supported,
)
from baraza.core.minutes import ActionItem, Decision, Minutes, OpenPoint, SourceRef, Topic
from baraza.core.segments import TranscriptSegment


def seg(i, speaker, text):
    return TranscriptSegment(meeting_id="m", segment_id=str(i), speaker=speaker, start=i, end=i + 1, text=text)


SEGS = [
    seg(0, "Alice", "On valide le budget de 5000 euros."),
    seg(1, "Alice", "Bob enverra le rapport avant le 15 octobre."),
    seg(2, "Bob Martin", "D'accord, je m'en occupe."),
    seg(3, "Chloé", "Je ferai la revue d'ici vendredi."),
]


def src(*idx):
    return SourceRef(segment_indices=list(idx))


def action(text="x", owner=None, due=None, idx=(1,)):
    return ActionItem(text=text, owner=owner, due_date=due, source=src(*idx))


def run(*actions, decisions=(), topics=(), open_points=(), meeting_date=None):
    m = Minutes(summary="s", decisions=list(decisions), actions=list(actions),
                topics=list(topics), open_points=list(open_points))
    return apply_anti_invention(m, SEGS, meeting_date)


def test_valid_action_untouched():
    out, corr = run(action("Rapport", "Bob", "2026-10-15", (1, 2)))
    assert corr == [] and out.actions[0].owner == "Bob" and out.actions[0].due_date == "2026-10-15"


def test_invented_owner_is_nulled_and_recorded():
    out, corr = run(action(owner="Zoé"))
    assert out.actions[0].owner is None
    assert [(c.kind, c.original_value, c.item_type) for c in corr] == [("owner_nulled", "Zoé", "action")]


def test_owner_known_as_speaker_is_kept_and_first_name_matches_full_name():
    assert run(action(owner="Bob", idx=(0,)))[1] == []          # Bob = "Bob Martin" (locuteur)
    assert run(action(owner="Bob Martin", idx=(0,)))[1] == []


def test_invented_date_is_nulled():
    out, corr = run(action(due="2026-11-30"))
    assert out.actions[0].due_date is None and corr[0].kind == "due_date_nulled"


def test_out_of_range_and_negative_indices_rejected_for_every_item_type():
    out, corr = run(
        action("a", idx=(99,)), action("b", idx=(-1,)),
        decisions=[Decision(text="d", source=src(42))],
        topics=[Topic(title="t", summary="s", source=src(7))],
        open_points=[OpenPoint(text="o", source=src(4))],      # 4 segments : index max = 3
    )
    assert out.actions == [] and out.decisions == [] and out.topics == [] and out.open_points == []
    assert [c.kind for c in corr] == ["item_rejected"] * 5
    assert {c.item_type for c in corr} == {"action", "decision", "topic", "open_point"}


def test_valid_decision_topic_open_point_kept():
    out, corr = run(
        decisions=[Decision(text="Budget validé", source=src(0))],
        topics=[Topic(title="Budget", summary="s", source=src(0))],
        open_points=[OpenPoint(text="Qui ?", source=src(3))],
    )
    assert corr == [] and len(out.decisions) == len(out.topics) == len(out.open_points) == 1


def test_positions_refer_to_the_original_list():
    _, corr = run(action("ok", idx=(1,)), action("bad", idx=(99,)), action("bad owner", owner="Zoé", idx=(1,)))
    assert [(c.kind, c.item_position) for c in corr] == [("item_rejected", 1), ("owner_nulled", 2)]


def test_input_is_not_mutated():
    m = Minutes(summary="s", actions=[action(owner="Zoé")])
    apply_anti_invention(m, SEGS)
    assert m.actions[0].owner == "Zoé"


# ---------------- année (cas réel : le modèle avait écrit 2023) ----------------
MEETING = date(2026, 10, 12)


def test_invented_year_replaced_with_meeting_year_and_recorded():
    out, corr = run(action(due="2023-10-15"), meeting_date=MEETING)
    assert out.actions[0].due_date == "2026-10-15"
    assert [(c.kind, c.original_value) for c in corr] == [("due_date_year_adjusted", "2023-10-15")]


def test_no_meeting_date_means_year_unchecked():
    assert run(action(due="2023-10-15"))[0].actions[0].due_date == "2023-10-15"


# ---------------- formats de date ----------------
def sup(due, text):
    return due_date_is_supported(due, normalize(text))


@pytest.mark.parametrize("due,text", [
    ("2026-10-15", "avant le 15 octobre"), ("2026-10-15", "avant le 15/10"),
    ("2026-10-01", "pour le 1er octobre"), ("2026-10-15", "by October 15th"),
    ("15/10/2026", "avant le 15 octobre"), ("15 octobre 2026", "avant le 15/10"),
    ("October 15, 2026", "avant le 15 octobre"), ("2026-10-15T00:00:00", "avant le 15 octobre"),
    ("vendredi", "On se voit vendredi."), ("next friday", "I'll do it next Friday."),
])
def test_dates_found(due, text):
    assert sup(due, text)


@pytest.mark.parametrize("due,text", [
    ("2026-11-15", "avant le 15 octobre"), ("2026-10-16", "avant le 15 octobre"),
    ("2026-10-05", "avant le 15 octobre"), ("2026-10-15", "un budget de 115/10 euros"),
    ("2026-10-15", "à la fin du mois"), ("vendredi", "on se voit lundi"), ("", "15 octobre"),
])
def test_dates_not_found(due, text):
    assert not sup(due, text)


def test_owner_helpers():
    assert owner_is_supported("  ALICE ", normalize("alice parle"), [])
    assert not owner_is_supported("Zoé", normalize("Alice dit bonjour"), ["Alice", "Bob"])
