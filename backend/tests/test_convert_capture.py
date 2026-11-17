import json
from pathlib import Path

import pytest

from baraza.core.transcript import Transcript
from scripts.convert_capture import main


def setup_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: object) -> Path:
    source = tmp_path / "fictional-export.json"
    output = tmp_path / "fictional-transcript.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "convert_capture",
            str(source),
            str(output),
            "--meeting-id",
            "fictional-meeting",
            "--title",
            "Fictional meeting",
            "--started-at",
            "2026-11-02T10:00:00Z",
            "--language",
            "en",
            "--participants-informed",
        ],
    )
    return output


def test_converter_preserves_source_times_and_unknown_speaker_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = setup_args(
        tmp_path,
        monkeypatch,
        {
            "segments": [
                {
                    "segment_id": "s1",
                    "speaker_id": "2",
                    "start_time": 1.5,
                    "end_time": 4,
                    "text": "Fictional statement.",
                }
            ]
        },
    )
    main()
    transcript = Transcript.model_validate_json(output.read_text("utf-8"))
    assert transcript.source_adapter == "segment_export"
    assert transcript.segments[0].speaker == "Speaker 2"
    assert (transcript.segments[0].start, transcript.segments[0].end) == (1.5, 4)


def test_converter_rejects_bad_timestamps_without_printing_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    marker = "fictional-private-marker"
    output = setup_args(
        tmp_path,
        monkeypatch,
        {
            "segments": [
                {
                    "segment_id": "s1",
                    "speaker_id": "2",
                    "start_time": 8,
                    "end_time": 1,
                    "text": marker,
                }
            ]
        },
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert marker not in str(error.value)
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    assert not output.exists()
