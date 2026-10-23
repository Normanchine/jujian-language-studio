"""Media removal preserves records and only uses the OS recycle bin."""
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
import study


class MediaRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in {"PROJECTS": self.root / "projects", "LAST": self.root / "last.txt",
                            "REMOVED_PROJECTS": self.root / "removed"}.items():
            patcher = patch.object(study, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.bridge = study.StudyBridge()
        self.addCleanup(self.bridge.close)

    def fixture(self, name="lesson", source="本地文件", **extra):
        media = self.root / (name + ".wav")
        with wave.open(str(media), "wb") as stream:
            stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0" * 8000)
        project = study.PROJECTS / (name + ".json")
        content = {"schema_version": 1, "title": name, "media_path": str(media),
                   "duration": 1, "source": source, "segments": [], **extra}
        project.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        return media, project

    def test_defaults_for_local_new_download_and_legacy_download(self):
        for i, (source, extra, expected) in enumerate([
                ("本地文件", {}, False),
                ("https://www.bilibili.com/video/BVtest", {}, True),
                ("https://www.xiaoyuzhoufm.com/episode/6888a0148e06fe8de74811af", {}, True),
                ("本地文件", {"media_origin": "download"}, True),
                ("https://www.bilibili.com/video/BVtest", {"media_origin": "local"}, False)]):
            _, project = self.fixture(str(i), source, **extra)
            self.assertEqual(self.bridge.deletionOptions(str(project))["defaultRecycle"], expected)

    def test_remove_only_preserves_original_and_exact_records(self):
        media, project = self.fixture()
        original_media, original_record = media.read_bytes(), project.read_bytes()
        with patch.object(study.QFile, "moveToTrash") as recycle:
            self.assertTrue(self.bridge.deleteProject(str(project), False))
            recycle.assert_not_called()
        self.assertEqual(media.read_bytes(), original_media)
        self.assertFalse(project.exists())
        self.assertEqual(next(study.REMOVED_PROJECTS.glob("*.json")).read_bytes(), original_record)

    def test_recycle_failure_restores_active_project(self):
        media, project = self.fixture()
        self.bridge.openProject(str(project))
        original = project.read_bytes()
        with patch.object(study.QFile, "moveToTrash", return_value=(False, "")):
            self.assertFalse(self.bridge.deleteProject(str(project), True))
        self.assertTrue(media.exists())
        self.assertEqual(project.read_bytes(), original)
        self.assertTrue(self.bridge.hasMedia)
        self.assertEqual(self.bridge._project_file, project)
        self.assertIn("无法移入", self.bridge.status)
        self.assertFalse(list(study.REMOVED_PROJECTS.glob("*.json")))

    def test_shared_missing_and_changed_files_are_rechecked(self):
        media, project = self.fixture()
        other = study.PROJECTS / "other.json"
        other.write_bytes(project.read_bytes())
        self.assertFalse(self.bridge.deletionOptions(str(project))["canRecycle"])
        with patch.object(study.QFile, "moveToTrash") as recycle:
            self.assertFalse(self.bridge.deleteProject(str(project), True))
            recycle.assert_not_called()
        other.unlink()
        self.assertTrue(self.bridge.deletionOptions(str(project))["canRecycle"])
        media.unlink()  # A file can disappear after the dialog opens.
        self.assertFalse(self.bridge.deleteProject(str(project), True))
        self.assertTrue(project.exists())
        self.assertTrue(self.bridge.deleteProject(str(project), False))

    def test_real_windows_recycle_bin_for_disposable_fixture(self):
        media, project = self.fixture("recycle-test")
        original = project.read_bytes()
        self.bridge.openProject(str(project))
        self.assertTrue(self.bridge.deleteProject(str(project), True), self.bridge.status)
        self.assertFalse(media.exists())
        self.assertFalse(project.exists())
        self.assertFalse(self.bridge.hasMedia)
        self.assertEqual(next(study.REMOVED_PROJECTS.glob("*.json")).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
