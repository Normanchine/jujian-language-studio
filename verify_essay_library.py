"""Render the essay library with copies of installed essays; never change originals."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
import shiboken6

import writing
from download_service import DownloadBridge
from model_settings import SettingsBridge
from study import StudyBridge
from writing import WritingBridge

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as directory:
    writing.ESSAYS = Path(directory) / "essays"
    writing.NOTES = Path(directory) / "notes"
    writing.FAVORITES = Path(directory) / "favorites.json"
    writing.ESSAYS.mkdir()
    for source in (root / "dist" / "每日日语" / "data" / "essays").glob("*.json"):
        shutil.copy2(source, writing.ESSAYS / source.name)
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    writer = WritingBridge()
    print("drafts_loaded", len(writer.drafts), flush=True)
    for name, bridge in {"study": StudyBridge(), "writer": writer,
                         "downloads": DownloadBridge(), "settings": SettingsBridge()}.items():
        engine.rootContext().setContextProperty(name, bridge)
    engine.load(QUrl.fromLocalFile(str(root / "qml" / "Main.qml")))
    if not engine.rootObjects():
        raise SystemExit("QML failed")
    window = engine.rootObjects()[0]
    quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    window.setProperty("page", "writing")
    if "--dialog" in sys.argv:
        def open_dialog():
            popup = window.findChild(QObject, "essayDeleteConfirm")
            view = window.findChild(QObject, "writingView")
            assert popup is not None
            assert view is not None
            view.setProperty("pendingDeleteTitle", "未命名作文")
            QMetaObject.invokeMethod(popup, "open")
        QTimer.singleShot(500, open_dialog)
    def capture():
        name = "preview-essay-delete-dialog.png" if "--dialog" in sys.argv else "preview-essay-library-feedback.png"
        quick.grabWindow().save(str(root / name))
        app.quit()
    QTimer.singleShot(1200, capture)
    app.exec()
