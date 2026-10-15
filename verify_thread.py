"""Check graceful stop and manual edits without invoking Ollama."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from threading import Event

from PySide6.QtCore import QCoreApplication, QTimer

import study


app = QCoreApplication([])
with tempfile.TemporaryDirectory(dir=study.DATA) as folder:
    temporary = Path(folder)
    study.PROJECTS = temporary / "projects"
    study.LAST = temporary / "last-project.txt"
    bridge = study.StudyBridge()
    bridge._project_file = temporary / "project.json"
    bridge._project = {
        "title": "test", "duration": 6.0,
        "segments": study.validate_segments([
            {"start": 0, "end": 2, "text": "今日はいい天気ですね。", "words": []},
            {"start": 2, "end": 4, "text": "明日は雨です。", "words": []},
            {"start": 4, "end": 6, "text": "今日は晴れです。", "words": []},
        ], 6.0),
    }
    for segment in bridge._project["segments"]:
        segment["translation"] = "人工译文"
    assert bridge.saveAnalysis("手动说明", "天気：天气")
    original = bridge._project["segments"][0]["analysis"].copy()
    bridge.startEnrichment(False)
    assert not bridge.enriching

    entered = Event()
    release = Event()
    called = []

    def explain(text: str, language: str = "ja") -> dict:
        called.append(text)
        entered.set()
        if not release.wait(5):
            raise TimeoutError("test model timed out")
        return {"grammar": "自动说明", "vocabulary": [], "source_text": text}

    study.explain = explain
    bridge.startEnrichment(True)
    assert bridge.enriching

    def stop() -> None:
        assert entered.is_set()
        bridge.stopEnrichment()
        assert bridge.enriching
        release.set()

    def finished() -> None:
        if not bridge.enriching:
            app.quit()

    bridge.stateChanged.connect(finished)
    QTimer.singleShot(100, stop)
    QTimer.singleShot(7000, app.quit)
    app.exec()
    bridge.close()

    saved = json.loads(bridge._project_file.read_text(encoding="utf-8"))
    assert called == ["明日は雨です。"], called
    assert saved["segments"][0]["analysis"] == original
    assert saved["segments"][1]["analysis"]["grammar"] == "自动说明"
    assert saved["segments"][2]["analysis"] == {}
    assert "已停止" in bridge.status, bridge.status
    bridge._read_enrichment(0, "今日はいい天気ですね。", {
        "grammar": "不应覆盖", "vocabulary": [], "source_text": "今日はいい天気ですね。",
    })
    assert bridge._project["segments"][0]["analysis"] == original
    print("graceful stop, per-sentence save, and manual priority: OK")
