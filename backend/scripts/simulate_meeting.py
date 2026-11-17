"""Feed the segment API with a fictional meeting, as a capture adapter would.

For demos and integration tests when no real Vexa capture is available. This does NOT validate
the real capture chain. Uses only the fictional fixture: never real transcripts.

    python backend/scripts/simulate_meeting.py <meeting_id> [--api URL] [--delay SECONDS]
"""

import argparse
import json
import time
from pathlib import Path

import httpx

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "fictional_meeting.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("meeting_id")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between segments")
    args = parser.parse_args()

    segments = json.loads(FIXTURE.read_text("utf-8"))["segments"]
    with httpx.Client(base_url=args.api, timeout=10) as client:
        for i, segment in enumerate(segments):
            payload = {
                "segment_id": f"sim-{i}",
                "speaker_id": str(i % 3 + 1),
                "speaker": segment["speaker"],
                "start_time": segment["start"],
                "end_time": segment["end"],
                "text": segment["text"],
            }
            response = client.post(f"/meetings/{args.meeting_id}/segments", json=[payload])
            response.raise_for_status()
            print(f"segment {i + 1}/{len(segments)} sent: {response.json()}")
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
