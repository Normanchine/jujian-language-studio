"""句间 — local listening, reading and writing study app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
import PySide6.QtMultimedia  # Ensure the frozen app includes Qt's media backend.
from PySide6.QtQml import QQmlApplicationEngine

from study import ASSETS, StudyBridge
from download_service import DownloadBridge
from model_settings import SettingsBridge
from writing import WritingBridge


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--transcribe-job":
        from transcribe_job import main as transcribe_main
        return transcribe_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--enrich-job":
        from enrich_job import main as enrich_main
        return enrich_main(sys.argv[2:])
    # The bundled Qt multimedia FFmpeg backend is preferred for local media.
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("句间")
    app.setOrganizationName("LocalStudy")
    app.setWindowIcon(QIcon(str(ASSETS / "assets" / "jujian.png")))
    bridge = StudyBridge()
    downloads = DownloadBridge()
    settings = SettingsBridge()
    writer = WritingBridge()
    app.aboutToQuit.connect(bridge.close)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("study", bridge)
    engine.rootContext().setContextProperty("downloads", downloads)
    engine.rootContext().setContextProperty("settings", settings)
    engine.rootContext().setContextProperty("writer", writer)
    engine.load(QUrl.fromLocalFile(str(ASSETS / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
