"""Isolated source/frozen application verification; invoked only with --release-check."""
def main():
    """Isolated real-media checks for completion, configurable keys and listening layout."""
    import json
    import os
    import subprocess
    import tempfile
    import sys
    import traceback
    from pathlib import Path
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")

    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PySide6.QtCore import QObject, QPointF, QPoint, Qt, QTimer, QUrl, QMetaObject, QCoreApplication
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow, QQuickItem
    from PySide6.QtTest import QTest
    from PySide6.QtMultimedia import QMediaPlayer
    import shiboken6
    import imageio_ffmpeg
    import model_settings
    import study
    import writing
    from download_service import DownloadBridge

    root = Path(__file__).resolve().parent
    captures = Path(os.environ.get("JUJIAN_CHECK_OUTPUT", str(Path.cwd() / "release-verification")))
    captures.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = (captures / "self-check.log").open("w", encoding="utf-8")
        sys.stderr = sys.stdout
    temporary = tempfile.TemporaryDirectory()
    data = Path(temporary.name)
    study.DATA, study.PROJECTS, study.LAST = data, data / "projects", data / "last.txt"
    study.REMOVED_PROJECTS = data / "removed"
    model_settings.CONFIG = data / "settings.json"
    writing.ESSAYS, writing.NOTES, writing.FAVORITES = data / "essays", data / "notes", data / "favorites.json"
    media = data / "video.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i",
                    "color=c=0x55786b:s=640x360:r=15", "-f", "lavfi", "-i",
                    "sine=frequency=220:sample_rate=44100", "-t", "3", "-c:v", "mpeg4",
                    "-c:a", "aac", str(media)], check=True, timeout=30)
    app = QGuiApplication([])
    bridge = study.StudyBridge()
    settings = model_settings.SettingsBridge()
    writer = writing.WritingBridge()
    downloads = DownloadBridge()
    from reading import ReadingBridge
    from toefl_listening import ToeflListeningBridge
    reading = ReadingBridge(data / "reading")
    toefl = ToeflListeningBridge(data / "toefl")
    assert settings.saveShortcuts("Alt+Left", "Alt+Right", "Space", "Ctrl+L")
    assert not settings.saveShortcuts("Space", "Space", "Space", "Space")
    assert model_settings.read_settings()["shortcut_next"] == "Alt+Right"
    assert settings.save(str(data / "downloads"), "", "", "local", "local", "local")
    assert model_settings.read_settings()["shortcut_next"] == "Alt+Right"
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda values: errors.extend(str(value.toString()) for value in values))
    for name, value in {"study": bridge, "settings": settings, "writer": writer, "downloads": downloads, "reading":reading, "toefl":toefl}.items():
        engine.rootContext().setContextProperty(name, value)
    engine.rootContext().setContextProperty("uiAnimationsEnabled", False)
    engine.load(QUrl.fromLocalFile(str(study.ASSETS / "qml/Main.qml")))
    assert engine.rootObjects(), errors
    window = engine.rootObjects()[0]
    assert window.property("appVersion") == "0.2.0"
    quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    player = window.findChild(QMediaPlayer, "mediaPlayer")
    frames = []
    player.videoSink().videoFrameChanged.connect(lambda frame: frames.append(1) if frame.isValid() else None)
    text = ("We learn a little bit about the past. And sooner or later, we realize that everything has a past. "
            "Nothing is without the past. Even the wisest person would not be where they are today without those experiences.")
    bridge.openMedia(str(media))
    bridge._project["language"] = "en"
    bridge._project["segments"] = study.validate_segments([
        {"start": 0, "end": 1.2, "text": "The first sentence."},
        {"start": 1.2, "end": 1.5, "text": text, "translation": "我们逐渐了解过去，也发现每个人都有自己的经历。"},
        *[{"start": 1.5 + i * 0.15, "end": 1.65 + i * 0.15,
           "text": "Every experience helps us understand the world a little better.",
           "translation": "每一次经历都让我们更了解这个世界。"} for i in range(10)]], 3.1, "en")
    bridge._save()
    bridge.segmentsChanged.emit()
    bridge.stateChanged.emit()
    failed = []

    def capture(name):
        assert quick.grabWindow().save(str(captures / (name + ".png")))

    def run_checks():
        try:
            window.setProperty("page", "settings")
            app.processEvents()
            field = window.findChild(QObject, "nextShortcut")
            item = shiboken6.wrapInstance(shiboken6.getCppPointer(field)[0], QQuickItem)
            point = item.mapToScene(QPointF(20, 18)).toPoint()
            QTest.mouseClick(quick, Qt.LeftButton, Qt.NoModifier, point)
            QTest.keyClick(quick, Qt.Key_D, Qt.ControlModifier)
            assert field.property("sequence") == "Ctrl+D", field.property("sequence")
            settings.saveShortcuts("Alt+Left", "Ctrl+D", "Space", "Ctrl+L")
            window.setProperty("page", "listen")
            quick.contentItem().forceActiveFocus()
            QTest.keyClick(quick, Qt.Key_D, Qt.ControlModifier)
            assert bridge.activeIndex == 1, bridge.activeIndex
            QTest.qWait(120)
            player.pause()
            app.processEvents()
            capture("split-wide")
            reading = window.findChild(QObject, "readingPane")
            assert reading.property("height") >= 200, reading.property("height")
            reading_list = window.findChild(QObject, "readingList")
            assert reading_list.property("count") == 12
            assert settings.savePlayerPreferences(600, 360)
            assert window.property("highlightDelayMs") == 600
            assert model_settings.read_settings()["highlight_delay_ms"] == 600
            settings.savePlayerPreferences(0, 360)
            before_height = window.property("videoHeight")
            divider = window.findChild(QObject, "videoDivider")
            divider_item = shiboken6.wrapInstance(shiboken6.getCppPointer(divider)[0], QQuickItem)
            point = divider_item.mapToScene(QPointF(100, 8)).toPoint()
            QTest.mousePress(quick, Qt.LeftButton, Qt.NoModifier, point)
            QTest.mouseMove(quick, point + QPointF(0, -60).toPoint(), 100)
            QTest.mouseRelease(quick, Qt.LeftButton, Qt.NoModifier, point + QPointF(0, -60).toPoint())
            assert window.property("videoHeight") < before_height - 20
            assert model_settings.read_settings()["listening_video_height"] == round(window.property("videoHeight"))
            list_item = shiboken6.wrapInstance(shiboken6.getCppPointer(reading_list)[0], QQuickItem)
            wheel_point = list_item.mapToScene(QPointF(100, 100))
            wheel = QWheelEvent(wheel_point, QPointF(quick.mapToGlobal(wheel_point.toPoint())),
                                QPoint(), QPoint(0, -120), Qt.NoButton, Qt.NoModifier,
                                Qt.NoScrollPhase, False)
            QCoreApplication.sendEvent(quick, wheel)
            assert not reading_list.property("followPlayback"), "Wheel browsing should pause follow"
            reading_list.setProperty("contentY", 0)
            QMetaObject.invokeMethod(reading_list, "cancelFlick")
            player.setPosition(round(bridge.segments[8]["start"] * 1000))
            player.pause()
            app.processEvents()
            assert not reading_list.property("followPlayback")
            assert abs(reading_list.property("contentY")) < 2
            assert QMetaObject.invokeMethod(reading_list, "returnToCurrent")
            QTest.qWait(320)
            assert reading_list.property("followPlayback")
            assert reading_list.property("contentY") > 100
            QMetaObject.invokeMethod(reading_list, "positionViewAtBeginning")
            QTest.qWait(60)
            card_point = list_item.mapToScene(QPointF(30, 30)).toPoint()
            QTest.mouseClick(quick, Qt.LeftButton, Qt.NoModifier, card_point)
            assert bridge.activeIndex == 0, "Clicking another card should seek to that sentence"
            bridge.chooseSentence(1); QTest.qWait(40); player.pause()
            QTimer.singleShot(300, large)
        except Exception as exc:
            failed.append(traceback.format_exc()); app.exit(1)

    def large():
        try:
            capture("split-dragged")
            window.setWidth(900); window.setHeight(640)
            QTimer.singleShot(300, narrow)
        except Exception as exc:
            failed.append(traceback.format_exc()); app.exit(1)

    def narrow():
        try:
            capture("stacked-narrow")
            assert window.findChild(QObject, "readingPane").property("y") > 100
            assert window.findChild(QObject, "readingPane").property("height") >= 120
            window.setHeight(820)
            QTimer.singleShot(300, finish)
        except Exception as exc:
            failed.append(traceback.format_exc()); app.exit(1)

    def finish():
        try:
            capture("stacked-tall")
            player.setPosition(max(0, player.duration() - 450))
            player.play()
            QTimer.singleShot(1500, completed)
        except Exception as exc:
            failed.append(traceback.format_exc()); app.exit(1)

    def completed():
        try:
            assert player.mediaStatus() == QMediaPlayer.EndOfMedia, player.mediaStatus()
            assert frames, "No video frames were decoded"
            saved = json.loads(bridge._project_file.read_text(encoding="utf-8"))
            assert saved["playback_completed"] is True, saved.get("playback_ms")
            bridge.savePlayback(0)
            bridge.refreshProjects()
            assert bridge.projects[0]["state"] == "已听完", bridge.projects[0]
            reopened = study.StudyBridge()
            assert reopened.projects[0]["state"] == "已听完"
            bridge.savePlayback(1000)
            bridge.refreshProjects()
            assert not bridge._project["playback_completed"]
            unexpected = [value for value in errors if 'PlaceholderText: Binding loop detected for property "width"' not in value]
            assert not unexpected, unexpected
            print("real EOF, keys, 12 cards, vertical divider, saved highlight delay, wheel/follow, card seek, normal/narrow: OK", flush=True)
            app.exit(0)
        except Exception as exc:
            failed.append(traceback.format_exc()); app.exit(1)

    QTimer.singleShot(1000, run_checks)
    QTimer.singleShot(12000, lambda: app.exit(3))
    code = app.exec()
    player.stop(); player.setSource(QUrl())
    engine.deleteLater(); app.processEvents()
    temporary.cleanup()
    print("failures", failed, "qml warnings", errors, flush=True)
    (captures / "result.json").write_text(json.dumps({"passed": code == 0, "failures": failed, "qml_warnings": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
    return code

if __name__ == "__main__":
    raise SystemExit(main())
