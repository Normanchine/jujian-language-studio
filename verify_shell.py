"""Load and render the new desktop shell at normal and narrow widths."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
import shiboken6

from download_service import DownloadBridge
from model_settings import SettingsBridge
from study import ASSETS, StudyBridge
from writing import WritingBridge

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
study = StudyBridge()
writer = WritingBridge()
downloads = DownloadBridge()
settings = SettingsBridge()
for name, value in {"study": study, "writer": writer, "downloads": downloads, "settings": settings}.items():
    engine.rootContext().setContextProperty(name, value)
engine.load(QUrl.fromLocalFile(str(ASSETS / "qml" / "Main.qml")))
if not engine.rootObjects():
    raise SystemExit("QML load failed")
window = engine.rootObjects()[0]
quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)


def capture() -> None:
    ok = quick.grabWindow().save(str(ASSETS / "preview-home-20261014.png"))
    window.setWidth(900)
    QTimer.singleShot(800, lambda: capture_narrow(ok))


def capture_narrow(previous: bool) -> None:
    ok = quick.grabWindow().save(str(ASSETS / "preview-home-narrow-20261014.png"))
    window.setProperty("sidebarCollapsed", True)
    QTimer.singleShot(400, lambda: capture_collapsed(previous, ok))


def capture_collapsed(normal: bool, narrow: bool) -> None:
    collapsed = quick.grabWindow().save(str(ASSETS / "design-preview" / "sidebar-collapsed.png"))
    print(f"home normal={normal} narrow={narrow} collapsed={collapsed} projects={len(study.projects)}", flush=True)
    app.exit(0 if normal and narrow and collapsed else 2)


QTimer.singleShot(1600, capture)
QTimer.singleShot(10000, lambda: app.exit(3))
raise SystemExit(app.exec())
