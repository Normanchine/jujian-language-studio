"""句间 — local listening, reading and writing study app."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter

STARTED = perf_counter()


def windows_animations_enabled() -> bool:
    """Respect the Windows client-area animation accessibility setting."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        enabled = ctypes.c_int(1)
        result = ctypes.windll.user32.SystemParametersInfoW(
            0x1042, 0, ctypes.byref(enabled), 0
        )
        return bool(enabled.value) if result else True
    except (AttributeError, OSError):
        return True


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--release-check":
        from release_check import main as check_main
        return check_main()
    if len(sys.argv) > 1 and sys.argv[1] == "--transcribe-job":
        from transcribe_job import main as transcribe_main
        return transcribe_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--enrich-job":
        from enrich_job import main as enrich_main
        return enrich_main(sys.argv[2:])
    # The bundled Qt multimedia FFmpeg backend is preferred for local media.
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PySide6.QtCore import QUrl, QTimer
    from PySide6.QtGui import QIcon
    import PySide6.QtMultimedia
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    from study import ASSETS, ROOT, StudyBridge
    from download_service import DownloadBridge
    from model_settings import SettingsBridge
    from writing import WritingBridge
    from reading import ReadingBridge

    milestones = {"imports_seconds": round(perf_counter() - STARTED, 3)}
    app = QApplication(sys.argv)
    app.setApplicationName("句间")
    app.setOrganizationName("LocalStudy")
    app.setWindowIcon(QIcon(str(ASSETS / "assets" / "jujian.png")))
    bridge = StudyBridge()
    downloads = DownloadBridge()
    settings = SettingsBridge()
    writer = WritingBridge()
    reading = ReadingBridge()
    app.aboutToQuit.connect(reading.leave)
    app.aboutToQuit.connect(bridge.close)
    app.aboutToQuit.connect(writer.pauseTask)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("study", bridge)
    engine.rootContext().setContextProperty("downloads", downloads)
    engine.rootContext().setContextProperty("settings", settings)
    engine.rootContext().setContextProperty("writer", writer)
    engine.rootContext().setContextProperty("reading", reading)
    engine.rootContext().setContextProperty("uiAnimationsEnabled", windows_animations_enabled())
    engine.load(QUrl.fromLocalFile(str(ASSETS / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    milestones["window_seconds"] = round(perf_counter() - STARTED, 3)

    def record_startup() -> None:
        import json
        from datetime import datetime
        milestones["event_loop_seconds"] = round(perf_counter() - STARTED, 3)
        milestones["time"] = datetime.now().isoformat(timespec="seconds")
        try:
            with (ROOT / "data" / "startup.log").open("a", encoding="utf-8") as log:
                log.write(json.dumps(milestones) + "\n")
        except OSError:
            pass

    QTimer.singleShot(0, record_startup)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(app.windowIcon(), app)
        tray.setToolTip("句间")
        menu = QMenu()

        def restore_window() -> None:
            window.showNormal()
            window.raise_()
            window.requestActivate()

        menu.addAction("打开句间", restore_window)
        menu.addSeparator()
        menu.addAction("退出句间", window.close)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: restore_window()
            if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                          QSystemTrayIcon.ActivationReason.DoubleClick) else None
        )
        tray.show()
        app.aboutToQuit.connect(tray.hide)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
