"""Check the feedback fixes using temporary data, without changing user drafts."""

import tempfile
from pathlib import Path

import model_settings
import writing


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    model_settings.CONFIG = root / "settings.json"
    settings = model_settings.SettingsBridge()
    assert settings.localFolder("file:///F:/Downloads/日本語") == "F:/Downloads/日本語"
    assert settings.save(str(root / "downloads"), "https://example.com/v1", "sample-model",
                         "cloud", "local", "cloud")
    reloaded = model_settings.SettingsBridge()
    assert reloaded.values["cloud_endpoint"] == "https://example.com/v1"
    assert reloaded.values["cloud_model"] == "sample-model"
    assert reloaded.values["writing_backend"] == "cloud"

    writing.ESSAYS = root / "essays"
    writing.NOTES = root / "notes"
    writing.FAVORITES = root / "favorites.json"
    writer = writing.WritingBridge()
    writer.newDraft("en")
    path = writer.currentPath
    writer.addCustomMaterials("although, however; because", "grammar")
    assert [item["expression"] for item in writer.materials] == ["although", "however", "because"]
    writer.setTargets('["although", "however", "although"]')
    assert writer.current["targets"] == ["although", "however"]
    writer.toggleDraftFavorite(path)
    assert writer.drafts[0]["favorite"]
    writer.openDraft(path)
    assert writer.current["favorite"]
    writer.deleteDraft(path)
    assert not Path(path).exists() and not writer.drafts

marks, _ = writing.validate_marks("The sun was shine.", [
    {"start_token": 2, "end_token": 2, "quote": "sun", "correction": "sun",
     "reason": "正确，无需修改", "kind": "error"},
])
assert not marks
marks, unanchored = writing.validate_marks("I watch TV.", [
    {"start_token": 99, "end_token": 99, "quote": "watch", "correction": "watched",
     "reason": "过去发生的事应使用过去式。", "kind": "error"},
])
assert len(marks) == 1 and marks[0]["start"] == 2 and not unanchored
print("feedback settings, draft library, batch cards, and legacy review filtering: OK")
