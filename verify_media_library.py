"""Exercise media library organization without touching installed user data."""

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication

import study


app = QCoreApplication([])
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    study.DATA = root
    study.PROJECTS = root / "projects"
    study.LAST = root / "last-project.txt"
    study.REMOVED_PROJECTS = root / "removed-projects"
    study.PROJECTS.mkdir()
    media = root / "lesson.mp3"
    media.write_bytes(b"unchanged media")
    project_file = study.PROJECTS / "lesson.json"
    project = {"schema_version": 1, "media_path": str(media), "title": "Lesson",
               "language": "ja", "duration": 30, "segments": []}
    project_file.write_text(json.dumps(project), encoding="utf-8")
    study.LAST.write_text(str(project_file), encoding="utf-8")

    bridge = study.StudyBridge()
    assert bridge.projects[0]["libraryLanguage"] == "日语"
    assert not bridge.projects[0]["favorite"]
    bridge._project_file = project_file
    bridge._project = project
    bridge.toggleProjectFavorite(str(project_file))
    bridge.setProjectLibraryLanguage(str(project_file), "en")
    saved = json.loads(project_file.read_text(encoding="utf-8"))
    assert saved["favorite"] is True
    assert saved["library_language"] == "en"
    assert saved["language"] == "ja"  # Library grouping must not change transcription.
    assert bridge._project["favorite"] is True
    assert bridge.projects[0]["libraryLanguage"] == "英语"

    bridge.deleteProject(str(root / "outside.json"))
    assert project_file.is_file()
    bridge.deleteProject(str(project_file))
    assert not project_file.exists()
    assert not study.LAST.exists()
    assert not bridge.hasMedia
    assert not bridge.projects
    archived = list(study.REMOVED_PROJECTS.glob("*.json"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text(encoding="utf-8")) == saved
    assert media.read_bytes() == b"unchanged media"
print("media library organization: OK")
