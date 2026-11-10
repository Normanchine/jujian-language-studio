"""Focused native desktop integration check; isolated data, silent local audio."""
import ctypes
import json
import os
from pathlib import Path
import sys
import traceback
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FOLDER = ROOT / "test-download/window-update-qt"
FOLDER.mkdir(parents=True, exist_ok=True)
os.environ["JUJIAN_DATA_DIR"] = str(FOLDER / "data")
os.environ["JUJIAN_WRITING_DEMO"] = "1"
from PySide6.QtCore import QObject, QTimer, Qt, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
import shiboken6
import app as application

warnings = []
qInstallMessageHandler(lambda kind, context, message: warnings.append(message)
                       if "file:///" in message or "failed" in message.lower() else None)
result = {}
original = application.use_windows_window_effects


def inspect_window(window):
    original(window)
    context = QQmlEngine.contextForObject(window)
    study = context.contextProperty("study")
    settings = context.contextProperty("settings")
    actions = context.contextProperty("windowActions")
    quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)

    def evaluate(code):
        expression = QQmlExpression(context, window, code)
        answer = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        return answer[0] if isinstance(answer, tuple) else answer

    def step(function, delay=300):
        def run():
            try:
                function()
            except Exception:
                result["failure"] = traceback.format_exc()
                actions.exit()
        QTimer.singleShot(delay, run)

    def startup():
        assert not window.findChild(QObject, "readingPageLoader").property("active")
        assert not window.findChild(QObject, "writingPageLoader").property("active")
        assert not window.findChild(QObject, "settingsPageLoader").property("active")
        assert "av" not in sys.modules and "keyring" not in sys.modules
        result["lazy_startup"] = True
        style = actions.frame.get_style(actions.frame.hwnd, -16)
        extended = actions.frame.get_style(actions.frame.hwnd, -20)
        assert style & 0x00CF0000 == 0x00CF0000
        assert not extended & 0x00080000, "layered window would prevent native transitions"
        result["native_caption_without_layered_opacity"] = True
        wav = FOLDER / "silent.wav"
        with wave.open(str(wav), "wb") as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000 * 16)
        study.openMedia(str(wav))
        transcript = FOLDER / "subtitle.json"
        transcript.write_text(json.dumps({"segments": [
            {"start": 0, "end": 8, "text": "来週の日曜日、引っ越しを手伝ってくれない？",
             "translation": "下周日能帮我搬家吗？", "analysis": {"source_text": "来週の日曜日、引っ越しを手伝ってくれない？", "grammar": "〜てくれない：委婉请求。",
                 "vocabulary": [{"surface": "引っ越し", "meaning": "搬家"}], "model": "manual"}},
            {"start": 8, "end": 16, "text": "いいけど、また引っ越すんだね。", "analysis": {"source_text": "いいけど、また引っ越すんだね。", "translation": "可以啊，不过你又要搬家了呀。"}}
        ]}, ensure_ascii=False), encoding="utf-8")
        study.importTranscript(str(transcript))
        assert study.sentenceCount == 2, study.status
        window.setProperty("page", "listen")
        step(copy_card)

    def copy_card():
        study.chooseSentence(0)
        evaluate("player.play()")
        QGuiApplication.clipboard().setText("before")
        QTest.keyClick(quick, Qt.Key_C, Qt.ControlModifier | Qt.ShiftModifier)
        copied = QGuiApplication.clipboard().text()
        assert "原文\n来週" in copied and "译文\n下周日" in copied
        assert "语法解析\n" in copied and "词汇\n引っ越し：搬家" in copied
        assert evaluate("player.playbackState === MediaPlayer.PlayingState")
        QTest.keyClick(quick, Qt.Key_Right, Qt.ControlModifier)
        QTest.keyClick(quick, Qt.Key_C, Qt.ControlModifier | Qt.ShiftModifier)
        assert "いいけど" in QGuiApplication.clipboard().text()
        assert "来週" not in QGuiApplication.clipboard().text()
        quick.grabWindow().save(str(FOLDER / "copy-listening.png"))
        evaluate("player.pause()")
        result["real_copy_shortcut_and_navigation_keeps_playing"] = True
        window.setProperty("page", "settings")
        step(settings_page)

    def settings_page():
        assert window.findChild(QObject, "copyShortcut")
        assert window.findChild(QObject, "closeBehaviorChoice")
        assert not settings.saveShortcuts("Ctrl+Left", "Ctrl+Right", "Space", "Ctrl+L", "Ctrl+R", "Ctrl+R")
        assert settings.saveShortcuts("Ctrl+Left", "Ctrl+Right", "Space", "Ctrl+L", "Ctrl+R", "Ctrl+Shift+C")
        quick.grabWindow().save(str(FOLDER / "settings.png"))
        QGuiApplication.clipboard().setText("settings-page")
        QTest.keyClick(quick, Qt.Key_C, Qt.ControlModifier | Qt.ShiftModifier)
        assert QGuiApplication.clipboard().text() == "settings-page"
        result["settings_and_shortcut_scope"] = True
        from model_settings import THEME_PALETTES
        window.setProperty("page", "home")
        for theme in THEME_PALETTES:
            assert settings.setTheme(theme)
            QTest.qWait(65)
            assert quick.grabWindow().save(str(FOLDER / ("home-" + theme + ".png")))
        result["fourteen_theme_home_renders"] = True
        settings.setTheme("sage")
        window.setProperty("page", "writing")
        step(writing_page)

    def writing_page():
        view = window.findChild(QObject, "writingView")
        assert view
        evaluate("writingView.openEditor()")
        assert not view.property("libraryMode")
        evaluate("writingView.showLibrary(); writingView.openEditor()")
        assert not view.property("libraryMode")
        assert evaluate("writingView.saveNow()")
        window.setProperty("page", "reading")
        step(reading_page)

    def reading_page():
        assert window.findChild(QObject, "readingHome")
        evaluate("readingView.showHome(); readingView.leavePage()")
        window.setProperty("page", "settings")
        result["lazy_pages_open_and_leave"] = True
        # Simulate a compositor/frame reset before leaving the normal state.
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        value = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(actions.frame.hwnd, 33, ctypes.byref(value), ctypes.sizeof(value))
        actions.minimize()
        step(minimized)

    def minimized():
        assert window.windowState() == Qt.WindowMinimized
        actions.restore()
        step(restored)

    def restored():
        assert window.windowState() == Qt.WindowNoState and window.isVisible()
        value = ctypes.c_int()
        dwm = ctypes.windll.dwmapi
        dwm.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        assert dwm.DwmGetWindowAttribute(actions.frame.hwnd, 33, ctypes.byref(value), ctypes.sizeof(value)) == 0
        assert value.value == 2, "rounded corner preference should recover after restore"
        result["corner_preference_recovers_after_restore"] = True
        result["normal_minimize_restore"] = True
        window.showMaximized()
        step(maximized)

    def maximized():
        assert window.windowState() == Qt.WindowMaximized
        quick.grabWindow().save(str(FOLDER / "maximized.png"))
        actions.minimize()
        step(max_minimized)

    def max_minimized():
        assert window.windowState() == Qt.WindowMinimized
        actions.restore()
        step(max_restored)

    def max_restored():
        assert window.windowState() == Qt.WindowMaximized
        result["maximized_minimize_restore"] = True
        assert settings.saveCloseBehavior("tray")
        if actions.trayAvailable:
            window.close()
            assert not window.isVisible()
            actions.restore()
            assert window.isVisible() and window.windowState() == Qt.WindowMaximized
            result["close_to_tray_and_restore_maximized"] = True
        else:
            result["close_to_tray_and_restore_maximized"] = "tray unavailable"
        # The tray Exit path must exit even with close_behavior=tray.
        result["tray_exit_requested"] = True
        actions.exit()

    step(startup, 450)


application.use_windows_window_effects = inspect_window
exit_code = application.main()
result["warnings"] = warnings
result["exit_code"] = exit_code
result["passed"] = not result.get("failure") and not warnings and result.get("tray_exit_requested", False)
(FOLDER / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["passed"] else 1)
