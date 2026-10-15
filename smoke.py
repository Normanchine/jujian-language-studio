"""Render and exercise the desktop app without controlling a browser."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
import shiboken6

from study import ROOT, StudyBridge


app = QGuiApplication(sys.argv)
bridge = StudyBridge()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("study", bridge)
engine.load(QUrl.fromLocalFile(str(ROOT / "qml" / "Main.qml")))
if not engine.rootObjects():
    raise SystemExit("QML load failed")
window = engine.rootObjects()[0]
player = window.findChild(QMediaPlayer, "mediaPlayer")
if player is None:
    raise SystemExit("QML media player missing")
reading_list = window.findChild(QQuickItem, "readingList")
if reading_list is None:
    raise SystemExit("QML reading list missing")


def start() -> None:
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    quick_window.grabWindow().save(str(ROOT / "preview-empty.png"))
    if bridge.hasMedia or bridge.sentenceCount != 0:
        app.exit(6)
        return
    bridge.openMedia(r"C:\Users\zyc15\Desktop\42694741937-1-30232.mp4")
    QTimer.singleShot(1200, begin_seek)


def begin_seek() -> None:
    print(f"sentences={bridge.sentenceCount} duration_ms={player.duration()} seekable={player.isSeekable()}", flush=True)
    if bridge.sentenceCount != 321 or not player.isSeekable():
        app.exit(2)
        return
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    QTest.mouseMove(quick_window, QPoint(145, 385))
    quick_window.grabWindow().save(str(ROOT / "preview-hover.png"))
    QTest.mouseClick(quick_window, Qt.LeftButton, Qt.NoModifier, QPoint(145, 385))
    QTimer.singleShot(850, verify_play_button)


def verify_play_button() -> None:
    print(f"play_button_position_ms={player.position()} state={player.playbackState()}", flush=True)
    if player.position() < 500:
        app.exit(7)
        return
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    QTest.mouseClick(quick_window, Qt.LeftButton, Qt.NoModifier, QPoint(145, 385))
    QTest.mouseClick(quick_window, Qt.LeftButton, Qt.NoModifier, QPoint(970, 285))
    QTimer.singleShot(1300, finish)


def finish() -> None:
    position = player.position()
    scroll_y = reading_list.property("contentY")
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    image = quick_window.grabWindow()
    saved = image.save(str(ROOT / "preview.png"))
    print(f"position_ms={position} active_index={bridge.activeIndex} scroll_y={scroll_y} preview_saved={saved}", flush=True)
    if position < 5200 or bridge.activeIndex != 1 or scroll_y < 100 or not saved:
        app.exit(3)
        return
    player.setPosition(round(bridge.segments[2]["start"] * 1000) - 300)
    QTimer.singleShot(1100, verify_auto_scroll)


def verify_auto_scroll() -> None:
    scroll_y = reading_list.property("contentY")
    print(f"auto_advance_index={bridge.activeIndex} scroll_y={scroll_y}", flush=True)
    if bridge.activeIndex != 2 or scroll_y < 210:
        app.exit(8)
        return
    bridge.chooseSentence(3)
    QTimer.singleShot(180, verify_scroll_motion)


def verify_scroll_motion() -> None:
    scroll_y = reading_list.property("contentY")
    print(f"scroll_after_change={scroll_y}", flush=True)
    if scroll_y < 300:
        app.exit(9)
        return
    QTimer.singleShot(600, finish_scroll_motion)


def finish_scroll_motion() -> None:
    scroll_y = reading_list.property("contentY")
    print(f"scroll_after_settle={scroll_y}", flush=True)
    if scroll_y < 300:
        app.exit(10)
        return
    bridge.chooseSentence(200)
    QTimer.singleShot(1200, finish_late)


def finish_late() -> None:
    expected = round(bridge.currentSentence["start"] * 1000)
    position = player.position()
    print(f"late_seek_ms={position} expected_start_ms={expected} active_index={bridge.activeIndex}", flush=True)
    player.pause()
    if bridge.activeIndex != 200 or not expected <= position <= expected + 2000:
        app.exit(5)
        return
    window.setWidth(1500)
    window.setHeight(950)
    bridge.chooseSentence(37)
    QTimer.singleShot(800, finish_large_preview)


def finish_large_preview() -> None:
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    saved = quick_window.grabWindow().save(str(ROOT / "preview-large.png"))
    print(f"large_preview_saved={saved} reading_height={reading_list.height()}", flush=True)
    player.pause()
    if not saved or reading_list.height() <= 500:
        app.exit(11)
        return
    segment = bridge._project["segments"][37]
    segment["analysis"] = {
        "grammar": "「〜はこんな感じです」：展示眼前事物并说明其大致状态。",
        "vocabulary": [{"surface": "ちなみに", "meaning": "顺便说一下"}],
        "model": "preview", "source_text": segment["text"],
    }
    bridge.segmentsChanged.emit()
    QTimer.singleShot(500, finish_notes_preview)


def finish_notes_preview() -> None:
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    saved = quick_window.grabWindow().save(str(ROOT / "preview-notes.png"))
    print(f"notes_preview_saved={saved}", flush=True)
    if not saved:
        app.exit(12)
        return
    bridge.chooseSentence(38)
    QTimer.singleShot(900, finish_next_after_notes)


def finish_next_after_notes() -> None:
    quick_window = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
    saved = quick_window.grabWindow().save(str(ROOT / "preview-scroll-notes.png"))
    print(f"next_after_notes_index={bridge.activeIndex} scroll_y={reading_list.property('contentY')} saved={saved}", flush=True)
    app.exit(0 if saved and bridge.activeIndex == 38 else 13)


QTimer.singleShot(1500, start)
QTimer.singleShot(22000, lambda: app.exit(4))
raise SystemExit(app.exec())
