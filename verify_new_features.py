"""Focused checks for imported media, progress, speech joins, and anchored marks."""

import json
from pathlib import Path

import study
from transcribe_job import merge_english_pauses
from writing import review_blocks, validate_marks

root = Path(__file__).resolve().parent
target = root / "test-download" / "verify-projects"
target.mkdir(exist_ok=True)
study.PROJECTS = target
study.LAST = root / "test-download" / "verify-last-project.txt"
audio = root / "test-download" / "集成测试音频.m4a"
video = root / "test-download" / "集成测试视频.mp4"
assert audio.is_file() and video.is_file()
bridge = study.StudyBridge()
bridge.registerDownloaded(str(audio), "Test audio", "https://www.bilibili.com/video/BV1KVWw61EYo", "")
bridge.registerDownloaded(str(video), "Test video", "https://www.bilibili.com/video/BV1KVWw61EYo", "")
assert len(bridge.projects) == 2
assert {entry["video"] for entry in bridge.projects} == {False, True}
audio_project = next(entry for entry in bridge.projects if not entry["video"])
assert audio_project["state"] == "未记录进度"
bridge.openProject(audio_project["path"])
bridge.savePlayback(120_000)
bridge.refreshProjects()
assert next(entry for entry in bridge.projects if not entry["video"])["state"] == "未听完"
bridge.savePlayback(bridge.durationMs - 500)
bridge.refreshProjects()
assert next(entry for entry in bridge.projects if not entry["video"])["state"] == "已听完"

raw = [
    {"start": 0.0, "end": 2.0, "text": "One thing I learned is", "words": [{"text": "One", "start": 0.0, "end": 0.2}]},
    {"start": 2.4, "end": 2.6, "text": "that", "words": [{"text": "that", "start": 2.4, "end": 2.6}]},
    {"start": 3.0, "end": 5.0, "text": "seeking helps me.", "words": [{"text": "seeking", "start": 3.0, "end": 3.3}]},
]
joined = merge_english_pauses(raw)
assert len(joined) == 1 and len(joined[0]["words"]) == 3 and len(raw) == 3

ja = study.validate_segments([
    {"start": 0, "end": 1, "text": "ここは何階ですか"},
    {"start": 1, "end": 2, "text": "男の人は何回に行きますか"},
], 2, "ja")
assert ja[1]["text"] == "男の人は何回に行きますか" and "階" in ja[1]["suggestion"]

original = "I choose myy boy. He go to school."
marks, stray = validate_marks(original, [
    {"start_token": 3, "end_token": 3, "start_char": 6, "end_char": 8,
     "quote": "myy", "correction": "my", "reason": "Spelling", "kind": "error"},
    {"start_token": 7, "end_token": 7, "quote": "go", "correction": "goes", "reason": "Agreement", "kind": "error"},
    {"start_token": 100, "end_token": 100, "quote": "boy", "correction": "", "reason": "Bad anchor", "kind": "error"},
])
assert len(marks) == 2 and len(stray) == 1
blocks = review_blocks(original, marks)
assert len(blocks) == 2 and sum(len(block["notes"]) for block in blocks) == 2
print(json.dumps({"projects": len(bridge.projects), "joined": len(joined),
                  "marks": len(marks), "fallback": len(stray)}, ensure_ascii=False))
