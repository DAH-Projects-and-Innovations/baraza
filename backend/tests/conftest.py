from pathlib import Path

import pytest

from baraza.adapters.file_import import import_transcript_json
from baraza.core.transcript import Transcript

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def transcript() -> Transcript:
    return import_transcript_json((FIXTURES / "fictional_meeting.json").read_text("utf-8"))
