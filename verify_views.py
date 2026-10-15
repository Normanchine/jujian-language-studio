"""Render the editor, teacher marks, library, and settings without touching user drafts."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
import shiboken6

import writing
from download_service import DownloadBridge
from model_settings import SettingsBridge
from study import ASSETS, StudyBridge
from writing import WritingBridge, validate_marks

writing.ESSAYS = ASSETS / "test-download" / "preview-essays"
writing.NOTES = ASSETS / "test-download" / "preview-notes"

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
study, writer, downloads, settings = StudyBridge(), WritingBridge(), DownloadBridge(), SettingsBridge()
for name, value in {"study": study, "writer": writer, "downloads": downloads, "settings": settings}.items():
    engine.rootContext().setContextProperty(name, value)
engine.load(QUrl.fromLocalFile(str(ASSETS / "qml" / "Main.qml")))
if not engine.rootObjects():
    raise SystemExit("QML load failed")
window = engine.rootObjects()[0]
quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)

writer.newDraft("en")
sample = "I choose myy boy. He go to school every day."
writer.saveDraft("An English practice essay", "A useful habit", sample)
writer._materials = [{"expression": "make a habit of", "kind": "vocabulary", "meaning": "养成习惯",
                      "example": "I make a habit of reading every day."}]
writer.changed.emit()

def capture(page, filename, next_step):
    window.setProperty("page", page)
    QTimer.singleShot(600, lambda: save(filename, next_step))

def save(filename, next_step):
    result = quick.grabWindow().save(str(ASSETS / filename))
    print(filename, result, flush=True)
    next_step()

def review():
    marks, _ = validate_marks(sample, [
        {"start_token": 3, "end_token": 3, "quote": "myy", "correction": "my", "reason": "删除多出的 y。", "kind": "error"},
        {"start_token": 7, "end_token": 7, "quote": "go", "correction": "goes", "reason": "He 是第三人称单数。", "kind": "error"},
    ])
    writer._draft["review"] = {"language": "en", "text": sample, "marks": marks,
                               "overall": "句子清楚；请留意拼写与主谓一致。", "targetFeedback": "本次练习未选目标表达。"}
    writer.changed.emit()
    writer.reviewReady.emit()
    def review_narrow():
        window.setWidth(900)
        capture("writing", "preview-writing-review-narrow-20261015.png", library_page)

    def library_page():
        window.setWidth(1180)
        capture("library", "preview-library-20261014.png",
                lambda: capture("settings", "preview-settings-20261014.png", lambda: app.exit(0)))

    QTimer.singleShot(600, lambda: save("preview-writing-review-20261014.png", review_narrow))

def writing_narrow():
    window.setWidth(900)
    capture("writing", "preview-writing-narrow-20261014.png", lambda: (window.setWidth(1180), review()))

QTimer.singleShot(900, lambda: capture("writing", "preview-writing-20261014.png", writing_narrow))
QTimer.singleShot(12000, lambda: app.exit(3))
raise SystemExit(app.exec())
