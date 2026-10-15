"""Check malformed Ollama responses and batch continuation without user data."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QTimer

import enrich_job
import study


source = "よく聞きますが 私は運動するともっと眠くなります"
valid = json.dumps({"grammar": "運動すると：运动之后。", "vocabulary": []}, ensure_ascii=False)
limits = []


def fake_urlopen(request, timeout):
    limits.append(json.loads(request.data)["options"]["num_predict"])
    response = '{"grammar": "unfinished' if len(limits) == 1 else valid
    return io.BytesIO(json.dumps({"response": response, "done_reason": "stop"}).encode("utf-8"))


with patch.object(enrich_job, "urlopen", side_effect=fake_urlopen):
    assert enrich_job.explain(source)["grammar"] == "運動すると：运动之后。"
assert limits == [384, 768], limits

with patch.object(enrich_job, "urlopen", side_effect=lambda request, timeout: io.BytesIO(
    json.dumps({"response": '{"grammar": "unfinished', "done_reason": "stop"}).encode("utf-8")
)):
    try:
        enrich_job.explain(source)
    except enrich_job.ModelResponseError:
        pass
    else:
        raise AssertionError("Two malformed responses were accepted")

app = QCoreApplication([])
with tempfile.TemporaryDirectory(dir=study.DATA) as folder:
    temporary = Path(folder)
    study.PROJECTS = temporary / "projects"
    study.LAST = temporary / "last-project.txt"
    bridge = study.StudyBridge()
    bridge._project_file = temporary / "project.json"
    bridge._project = {
        "title": "test", "duration": 4.0,
        "segments": study.validate_segments([
            {"start": 0, "end": 2, "text": source, "words": []},
            {"start": 2, "end": 4, "text": "今日は晴れです。", "words": []},
        ], 4.0),
    }

    def fake_explain(text, language="ja"):
        if text == source:
            raise enrich_job.ModelResponseError("bad JSON")
        return {"grammar": "晴れです：是晴天。", "vocabulary": []}

    study.explain = fake_explain
    study.translate = lambda text: "测试译文"

    def check():
        if not bridge.enriching:
            app.quit()

    bridge.stateChanged.connect(check)
    QTimer.singleShot(0, lambda: bridge.startEnrichment(True))
    QTimer.singleShot(3000, app.quit)
    app.exec()
    bridge.close()
    saved = json.loads(bridge._project_file.read_text(encoding="utf-8"))
    assert saved["segments"][0]["analysis"] == {}
    assert saved["segments"][1]["analysis"]["grammar"] == "晴れです：是晴天。"
    assert bridge._enrich_failed == 1 and bridge._enrich_done == 1
    print("malformed JSON retry and batch continuation: OK")
