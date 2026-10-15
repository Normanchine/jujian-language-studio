"""Check draft, target, favorite, review, and note separation in test storage."""

import json
from pathlib import Path

import writing

test = Path(__file__).resolve().parent / "test-download" / "writing-store"
writing.ESSAYS = test / "essays"
writing.NOTES = test / "notes"
writing.FAVORITES = test / "favorites.json"

bridge = writing.WritingBridge()
bridge.newDraft("en")
bridge.setMode("toefl_email")
bridge.saveDraft("Practice", "An email", "I choose myy boy.")
bridge.setTargets(json.dumps(["make a habit of"]))
bridge._materials = [{"expression": "make a habit of", "kind": "vocabulary",
                      "meaning": "养成习惯", "example": "I make a habit of reading."}]
bridge.toggleFavorite("make a habit of")
path = Path(bridge.currentPath)
snapshot = dict(bridge.current)
assert snapshot["text"] == "I choose myy boy."
assert snapshot["writing_mode"] == "toefl_email"
assert snapshot["targets"] == ["make a habit of"]
assert bridge.favorites[0]["expression"] == "make a habit of"
bridge.addNote("拼写时检查重复字母。", "myy")
reopened = writing.WritingBridge()
reopened.openDraft(str(path))
assert reopened.current["text"] == snapshot["text"]
assert reopened.favorites[0]["expression"] == "make a habit of"
assert reopened.notes[0]["sourceQuote"] == "myy"
print("writing persistence: OK")
