from itertools import product

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.core.meetings import InvalidMeetingTransition, MeetingStatus, check_transition
from baraza.storage.captures import SqlCaptureStore

# Explicit expectations independent from the implementation's transition table.
ALLOWED = {
    ("pending", "capturing"),
    ("pending", "processing"),
    ("pending", "error"),
    ("capturing", "processing"),
    ("capturing", "error"),
    ("processing", "draft_ready"),
    ("processing", "error"),
    ("draft_ready", "validated"),
    ("draft_ready", "error"),
    ("error", "pending"),
}


@pytest.mark.parametrize(("source", "target"), list(product(MeetingStatus, repeat=2)))
def test_all_transitions(source, target):
    if (source, target) in ALLOWED:
        check_transition(source, target)
    else:
        with pytest.raises(InvalidMeetingTransition, match=f"{source} -> {target}"):
            check_transition(source, target)


async def test_transition_history_survives_store_restart(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'meetings.db'}")
    store = SqlCaptureStore(engine)
    await store.create("m1")
    for state in ["capturing", "processing", "draft_ready", "validated"]:
        await store.transition("m1", MeetingStatus(state))
    reloaded = await SqlCaptureStore(engine).get("m1")
    assert reloaded.status == MeetingStatus.VALIDATED
    assert [t.to_status for t in reloaded.transitions] == [
        "pending",
        "capturing",
        "processing",
        "draft_ready",
        "validated",
    ]
    assert all(t.at.utcoffset().total_seconds() == 0 for t in reloaded.transitions)
    assert reloaded.transitions == sorted(reloaded.transitions, key=lambda t: t.at)
    with pytest.raises(InvalidMeetingTransition):
        await store.transition("m1", MeetingStatus.CAPTURING)
    assert await store.get("m1") == reloaded
    await engine.dispose()
