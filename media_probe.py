"""Small native media check before building the desktop UI."""

import sys

from PySide6.QtCore import QCoreApplication, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


def main() -> int:
    app = QCoreApplication(sys.argv)
    player = QMediaPlayer()
    audio = QAudioOutput()
    audio.setVolume(0)
    player.setAudioOutput(audio)
    target = 4780
    started = False

    def on_status(status: QMediaPlayer.MediaStatus) -> None:
        nonlocal started
        if status == QMediaPlayer.MediaStatus.LoadedMedia and not started:
            started = True
            print(f"loaded duration_ms={player.duration()} seekable={player.isSeekable()}", flush=True)
            player.setPosition(target)
            player.play()
            QTimer.singleShot(1700, finish)

    def finish() -> None:
        first = player.position()
        player.pause()
        player.setPosition(8780)
        print(f"played_position_ms={first} second_seek_ms={player.position()}", flush=True)
        app.exit(0 if first >= target + 700 and abs(player.position() - 8780) < 500 else 2)

    player.mediaStatusChanged.connect(on_status)
    player.errorOccurred.connect(lambda error, message: print(f"error={error} {message}", flush=True))
    QTimer.singleShot(12000, lambda: (print("timeout", flush=True), app.exit(3)))
    player.setSource(QUrl.fromLocalFile(r"C:\Users\zyc15\Desktop\42694741937-1-30232.mp4"))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
