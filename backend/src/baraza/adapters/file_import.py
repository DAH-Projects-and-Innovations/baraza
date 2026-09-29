"""File import adapter (fallback path, works for any platform).

For now only a JSON transcript in the common format is supported.
TODO: audio/video via faster-whisper + pyannote.audio.
"""

from baraza.core.transcript import Transcript


def import_transcript_json(raw: bytes | str) -> Transcript:
    return Transcript.model_validate_json(raw)
