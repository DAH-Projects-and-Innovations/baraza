"""Convert a segment export to the common transcript without guessing missing metadata.

Input is {"segments": [...]} using the streaming segment contract (including the
start_time/end_time aliases). Keep real input/output outside the repository.
This converter does not start or validate a real Meet capture.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from baraza.core.ingestion import normalize_raw_segment
from baraza.core.segments import TranscriptSegment, segments_to_transcript
from baraza.core.transcript import MeetingMetadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--meeting-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--started-at", required=True, type=datetime.fromisoformat)
    parser.add_argument("--language", required=True, choices=["en", "fr"])
    parser.add_argument("--participants-informed", action="store_true", required=True)
    args = parser.parse_args()
    try:
        raw = json.loads(args.input.read_text("utf-8"))
        segments = [
            TranscriptSegment.model_validate(
                {**normalize_raw_segment(segment), "meeting_id": args.meeting_id}
            )
            for segment in raw["segments"]
        ]
        transcript = segments_to_transcript(
            segments,
            MeetingMetadata(title=args.title, started_at=args.started_at, platform="google_meet"),
            language=args.language,
            source_adapter="segment_export",
        )
    except (ValueError, TypeError, KeyError):
        # Pydantic tracebacks include the submitted input; never print transcript text.
        raise SystemExit(
            "Invalid capture export. Check segment IDs, text, speaker metadata and timestamps."
        ) from None
    args.output.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
    print(f"Validated {len(transcript.segments)} final segments. Review speaker/timestamp gaps.")


if __name__ == "__main__":
    main()
