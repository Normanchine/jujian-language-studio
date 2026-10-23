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


def use_windows_window_effects(window) -> None:
    """Ask DWM for a subtle shadow and rounded corners on the custom frame."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        class Margins(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int) for name in ("left", "right", "top", "bottom")]

        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        # DWMWA_NCRENDERING_POLICY = 2, DWMNCRP_ENABLED = 2.
        render_policy = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(render_policy), ctypes.sizeof(render_policy))
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2.
        corners = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corners), ctypes.sizeof(corners))
        dwm.DwmExtendFrameIntoClientArea.argtypes = [ctypes.c_void_p, ctypes.POINTER(Margins)]
        dwm.DwmExtendFrameIntoClientArea.restype = ctypes.c_long
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(Margins(1, 1, 1, 1)))
    except (AttributeError, OSError, ValueError):
        pass


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
    from PySide6.QtCore import QUrl, QTimer, QLockFile
    from PySide6.QtGui import QIcon
    import PySide6.QtMultimedia
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox
    from study import ASSETS, ROOT, StudyBridge
    from download_service import DownloadBridge
    from model_settings import SettingsBridge
    from writing import WritingBridge
    from reading import ReadingBridge

    milestones = {"imports_seconds": round(perf_counter() - STARTED, 3)}
    app = QApplication(sys.argv)
    from core.paths import DATA
    from core.storage import DataStore
    DATA.parent.mkdir(parents=True, exist_ok=True)
    data_lock = QLockFile(str(DATA.with_name(DATA.name + '.lock')))
    data_lock.setStaleLockTime(0)
    if not data_lock.tryLock(0):
        QMessageBox.warning(None, '句间', '此数据目录已由另一个句间进程使用：\n' + str(DATA))
        return 1
    try:
        DataStore(DATA).apply_pending()
    except Exception as exc:
        QMessageBox.critical(None, '数据恢复未完成', str(exc) + '\n原记录和恢复材料已保留；请检查备份目录。')
        return 1
    milestones["data_ready_seconds"] = round(perf_counter() - STARTED, 3)
    app.setApplicationName("句间")
    app.setOrganizationName("LocalStudy")
    app.setWindowIcon(QIcon(str(ASSETS / "assets" / "jujian.png")))
    bridge = StudyBridge()
    downloads = DownloadBridge()
    settings = SettingsBridge()
    writer = WritingBridge()
    reading = ReadingBridge()
    milestones["bridges_ready_seconds"] = round(perf_counter() - STARTED, 3)
    settings.dataSafety.essaysRestored.connect(writer.refresh)
    QTimer.singleShot(1500, settings.dataSafety.automaticBackup)
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
    use_windows_window_effects(window)
    milestones["window_seconds"] = round(perf_counter() - STARTED, 3)

    def record_startup() -> None:
        import json
        from datetime import datetime
        milestones["event_loop_seconds"] = round(perf_counter() - STARTED, 3)
        milestones["time"] = datetime.now().isoformat(timespec="seconds")
        try:
            with (DATA / "startup.log").open("a", encoding="utf-8") as log:
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
