"""Exercise the local model subprocess and per-sentence persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer

import study


app = QCoreApplication([])
with tempfile.TemporaryDirectory(dir=study.ROOT / "data") as temporary:
    temp = Path(temporary)
    study.DATA = temp
    study.PROJECTS = temp / "projects"
    study.LAST = temp / "last-project.txt"
    bridge = study.StudyBridge()
    bridge._project_file = temp / "project.json"
    bridge._project = {
        "title": "test", "duration": 5.0,
        "segments": study.validate_segments([
            {"start": 0, "end": 2, "text": "今日はいい天気ですね。", "words": []}
        ], 5.0),
    }
    completed = False
    phase = "translation"

    def check() -> None:
        global completed, phase
        if bridge.enriching:
            return
        saved = json.loads(bridge._project_file.read_text(encoding="utf-8"))
        analysis = saved["segments"][0]["analysis"]
        if phase == "translation":
            assert analysis["translation"]
            assert analysis["translation_model"] == study.MODEL
            phase = "pending_analysis"
            QTimer.singleShot(100, begin_analysis)
            return
        if phase == "pending_analysis":
            return
        print(f"status={bridge.status}")
        print(f"analysis={analysis}")
        completed = bool(analysis.get("vocabulary") or analysis.get("grammar"))
        bridge.stateChanged.disconnect(check)
        if completed:
            assert bridge.saveAnalysis("ですね：共感を求める語尾。", "天気：天气")
            corrected = json.loads(bridge._project_file.read_text(encoding="utf-8"))
            reloaded = study.validate_segments(corrected["segments"], 5.0)
            assert reloaded[0]["analysis"]["model"] == "manual"
            assert reloaded[0]["analysis"]["vocabulary"][0]["surface"] == "天気"
        app.quit()

    def begin_analysis() -> None:
        global phase
        phase = "analysis"
        bridge.startEnrichment(False)

    bridge.stateChanged.connect(check)
    QTimer.singleShot(0, lambda: bridge.startTranslation(False))
    QTimer.singleShot(60000, app.quit)
    app.exec()
    bridge.close()
    if not completed:
        raise SystemExit("enrichment did not persist a result")
