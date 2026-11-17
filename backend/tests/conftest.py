from pathlib import Path

import pytest

from baraza.adapters.file_import import import_transcript_json
from baraza.config import get_settings
from baraza.core.transcript import Transcript

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def transcript() -> Transcript:
    return import_transcript_json((FIXTURES / "fictional_meeting.json").read_text("utf-8"))


@pytest.fixture(autouse=True)
def sign_in_switched_off(monkeypatch: pytest.MonkeyPatch):
    """Most tests are about meetings, not about who is asking: run them signed in as nobody.

    ``tests/test_auth.py`` switches sign in back on.
    """
    monkeypatch.setenv("BARAZA_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
