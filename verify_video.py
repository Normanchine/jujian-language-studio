"""Exercise local video rendering and seeking with a generated media fixture."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import av
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink

from study import inspect_media


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "data" / "video-fixture.mp4"


def create_fixture() -> None:
    with av.open(str(FIXTURE), "w") as output:
        video = output.add_stream("mpeg4", rate=20)
        video.width, video.height = 320, 180
        video.pix_fmt = "yuv420p"
        audio = output.add_stream("aac", rate=44100)
        audio.layout = "mono"
        for index in range(40):
            pixels = np.zeros((180, 320, 3), dtype=np.uint8)
            pixels[:, :, 0] = 160 if index < 20 else 40
            pixels[:, :, 1] = 60 if index < 20 else 180
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            for packet in video.encode(frame):
                output.mux(packet)
        for packet in video.encode():
            output.mux(packet)
        for index in range(20):
            count = 4410
            ticks = (np.arange(count) + index * count) / 44100
            wave = (np.sin(ticks * 2 * np.pi * 440) * 3000).astype(np.int16).reshape(1, -1)
            frame = av.AudioFrame.from_ndarray(wave, format="s16", layout="mono")
            frame.sample_rate = 44100
            for packet in audio.encode(frame):
                output.mux(packet)
        for packet in audio.encode():
            output.mux(packet)


def main() -> int:
    create_fixture()
    has_video, duration = inspect_media(FIXTURE)
    assert has_video and duration >= 1.9
    app = QGuiApplication(sys.argv)
    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    player.setAudioOutput(QAudioOutput())
    player.setSource(QUrl.fromLocalFile(str(FIXTURE)))
    frames = []
    sink.videoFrameChanged.connect(lambda frame: frames.append(frame) if frame.isValid() else None)

    def seek() -> None:
        player.setPosition(1200)
        player.play()

    def finish() -> None:
        print(f"duration_ms={player.duration()} position_ms={player.position()} frames={len(frames)} error={player.errorString()}")
        app.exit(0 if player.isSeekable() and player.position() >= 1400 and frames else 2)

    QTimer.singleShot(700, seek)
    QTimer.singleShot(1600, finish)
    QTimer.singleShot(5000, lambda: app.exit(3))
    result = app.exec()
    player.stop()
    player.setSource(QUrl())
    player.setVideoSink(None)
    player.setAudioOutput(None)
    player.deleteLater()
    app.processEvents()
    FIXTURE.unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
