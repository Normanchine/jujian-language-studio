"""Offline download naming, UI binding, and library registration regression."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import download_service
import study


class DownloadNamingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing = QGuiApplication.instance()
        if existing is not None and not isinstance(existing, QGuiApplication):
            raise unittest.SkipTest("Run this GUI test separately from QCoreApplication tests")
        cls.app = existing or QGuiApplication([])

    def test_edit_survives_progress_and_format_notifications(self):
        bridge = download_service.DownloadBridge()
        engine = QQmlEngine()
        engine.rootContext().setContextProperty("downloads", bridge)
        component = QQmlComponent(engine)
        component.setData(b'import QtQuick; TextInput { text: downloads.title }', QUrl())
        field = component.create()
        self.assertIsNotNone(field, component.errors())
        try:
            bridge._inspected({"title": "Original", "thumbnail": "", "formats": [{"id": "audio", "kind": "audio"}]})
            # TextInput.insert follows the editing path, retaining the QML binding.
            field.remove(0, len(field.property("text")))
            field.insert(0, "Custom title")
            for progress in (0.1, 0.5, 0.9):
                bridge._set_progress(progress)
                self.app.processEvents()
                self.assertEqual(field.property("text"), "Custom title")
            jobs = []
            with patch.object(bridge, "_launch", jobs.append):
                bridge.start(0, field.property("text"))
            self.assertEqual(jobs[0].name, "Custom title")
            bridge._inspected({"title": "Next video", "thumbnail": "", "formats": []})
            self.assertEqual(field.property("text"), "Next video")
        finally:
            field.deleteLater()
            self.app.processEvents()

    def test_custom_name_reaches_file_and_library_with_collision(self):
        import yt_dlp
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            fixture = folder / "fixture.wav"
            import wave
            with wave.open(str(fixture), "wb") as stream:
                stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                stream.writeframes(b'\0\0' * 8000)
            # Use a real audio container, avoiding network and server title drift.
            media_bytes = fixture.read_bytes()
            (folder / "My title.m4a").write_bytes(b"existing file")

            class Client:
                def __init__(self, options): self.options = options
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def extract_info(self, url, download):
                    Path(self.options["outtmpl"].replace("%(ext)s", "m4a")).write_bytes(media_bytes)
                    return {"title": "Bilibili original title"}

            result, errors = [], []
            job = download_service.DownloadJob("https://www.bilibili.com/video/test", "download",
                                                {"id": "audio", "kind": "audio"}, "My title")
            job.completed.connect(lambda *args: result.append(args))
            job.failed.connect(errors.append)
            with patch.object(download_service, "read_settings", return_value={"download_dir": str(folder)}), \
                 patch.object(yt_dlp, "YoutubeDL", Client):
                job.run()
            self.assertFalse(errors, errors)
            self.assertEqual(Path(result[0][0]).stem, "My title (2)")
            self.assertEqual(result[0][1], "My title (2)")
            with patch.object(study, "PROJECTS", folder / "projects"), \
                 patch.object(study, "LAST", folder / "last.txt"):
                bridge = study.StudyBridge()
                bridge.registerDownloaded(*result[0])
                self.assertEqual(bridge.projects[0]["title"], "My title (2)")
                bridge.close()


if __name__ == "__main__":
    unittest.main()
