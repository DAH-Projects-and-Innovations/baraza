"""Export the language-neutral contracts; use --check in CI to detect drift."""

import argparse
import json
from pathlib import Path

from baraza.core.segments import SEGMENT_SCHEMA_VERSION, TranscriptSegment
from baraza.core.transcript import SCHEMA_VERSION, Transcript

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for name, version, model in [
        ("transcript", SCHEMA_VERSION, Transcript),
        ("transcript-segment", SEGMENT_SCHEMA_VERSION, TranscriptSegment),
    ]:
        path = ROOT / "docs" / "schemas" / f"{name}-{version}.json"
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        content = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
        if args.check:
            if not path.exists() or path.read_text("utf-8") != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if stale:
        raise SystemExit("Outdated schemas: " + ", ".join(stale))


if __name__ == "__main__":
    main()
