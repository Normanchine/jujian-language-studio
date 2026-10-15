"""Exercise the selected Bilibili audio format through DownloadJob."""

from pathlib import Path
import sys

import download_service
from download_service import DownloadJob, available_formats

target = Path(__file__).resolve().parent / "test-download"
target.mkdir(exist_ok=True)
download_service.read_settings = lambda: {"download_dir": str(target)}

url = "https://www.bilibili.com/video/BV1KVWw61EYo"
inspection = DownloadJob(url, "inspect")
metadata = []
inspection.inspected.connect(metadata.append)
inspection.failed.connect(lambda message: print("inspect-error:", message, flush=True))
inspection.run()
if not metadata:
    raise SystemExit(2)
choices = metadata[0]["formats"]
mode = sys.argv[1] if len(sys.argv) > 1 else "audio"
choice = next((item for item in choices if item["id"] == "30216"), None) if mode == "audio" else next(
    (item for item in choices if item["kind"] == "video" and "360p" in item["label"]), None)
if not choice:
    raise SystemExit("expected format not available")
print("formats:", len(choices), "selected:", choice, flush=True)

job = DownloadJob(url, "download", choice, "集成测试音频" if mode == "audio" else "集成测试视频")
finished = []
job.completed.connect(lambda *args: finished.append(args))
job.failed.connect(lambda message: print("download-error:", message, flush=True))
job.run()
if not finished:
    raise SystemExit(3)
from study import inspect_media

path = Path(finished[0][0])
print("result:", path.name, path.stat().st_size, inspect_media(path),
      "cover:", bool(finished[0][3]), flush=True)
