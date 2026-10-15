"""Check English transcription selection and word display without loading Whisper."""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QCoreApplication

import transcribe_job
import study
from linguistics import display_tokens


class FakeModel:
    def __init__(self, expected_language):
        self.expected_language = expected_language

    def transcribe(self, audio, **kwargs):
        assert kwargs["language"] == self.expected_language
        assert kwargs["task"] == "transcribe"
        return {"language": "en", "segments": [{
            "start": 0.0, "end": 1.0, "text": "I can hear it.",
            "words": [{"start": 0.0, "end": 0.2, "word": "I"},
                      {"start": 0.2, "end": 0.5, "word": "can"},
                      {"start": 0.5, "end": 0.75, "word": "hear"},
                      {"start": 0.75, "end": 1.0, "word": "it."}],
        }]}


with tempfile.TemporaryDirectory() as folder:
    output = Path(folder) / "transcript.json"
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    for setting, expected in (("en", "en"), ("auto", None)):
        fake_whisper = SimpleNamespace(load_model=lambda *args, **kwargs: FakeModel(expected))
        with patch.dict(sys.modules, {"torch": fake_torch, "whisper": fake_whisper}), patch.object(
            transcribe_job, "read_audio", return_value=np.zeros(16000, dtype=np.float32)
        ):
            assert transcribe_job.main(["unused.wav", str(output), folder, setting]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["language"] == "en"
    segment = result["segments"][0]
    tokens = display_tokens(segment["text"], segment["words"], "en")
    assert [token["text"] for token in tokens] == ["I", "can", "hear", "it."]
    assert tokens[2]["start"] == 0.5
    app = QCoreApplication([])
    study.DATA = Path(folder)
    study.PROJECTS = Path(folder) / "projects"
    study.LAST = Path(folder) / "last-project.txt"
    bridge = study.StudyBridge()
    bridge._project_file = Path(folder) / "project.json"
    bridge._project = {"duration": 1.0, "language": "ja", "segments": []}
    assert bridge.transcriptionLanguage == "auto"
    bridge.setTranscriptionLanguage("en")
    assert bridge.contentLanguage == "ja"  # Selecting a language does not alter current subtitles.
    bridge._finish_transcription(0, output)
    assert bridge.contentLanguage == "en"
    assert [token["text"] for token in bridge.segments[0]["tokens"]] == ["I", "can", "hear", "it."]
    bridge.close()
    print("English transcription selection and word timing: OK")
