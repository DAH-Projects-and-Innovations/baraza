from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from baraza.core.segments import TranscriptSegment, segments_to_transcript
from baraza.core.transcript import MeetingMetadata


def make(**overrides: object) -> TranscriptSegment:
    data: dict[str, object] = {
        "meeting_id": "m1",
        "segment_id": "s1",
        "speaker": "Awa Example",
        "start": 0,
        "end": 4.5,
        "text": "Hello everyone.",
    }
    return TranscriptSegment.model_validate(data | overrides)


def test_valid_segment_defaults() -> None:
    segment = make()
    assert segment.is_final is True
    assert segment.language is None


def test_text_is_stripped() -> None:
    assert make(text="  Hello  ").text == "Hello"


@pytest.mark.parametrize(
    "overrides",
    [
        {"text": "   "},
        {"meeting_id": ""},
        {"segment_id": " "},
        {"speaker": ""},
        {"start": -1},
        {"start": 10, "end": 5},
        {"end": "soon"},
    ],
)
def test_invalid_segments_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make(**overrides)


def test_zero_length_segment_is_allowed() -> None:
    assert make(start=3, end=3).end == 3


def test_segments_to_transcript_keeps_final_segments_in_order() -> None:
    meeting = MeetingMetadata(
        title="Fictional sync",
        started_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        platform="google_meet",
    )
    segments = [
        make(segment_id="b", start=10, end=12, text="Second."),
        make(segment_id="a", start=0, end=5, text="First."),
        make(segment_id="c", start=12, end=14, text="Still talking", is_final=False),
    ]
    transcript = segments_to_transcript(segments, meeting, language="en", source_adapter="vexa")
    assert [s.text for s in transcript.segments] == ["First.", "Second."]
    assert transcript.source_adapter == "vexa"
