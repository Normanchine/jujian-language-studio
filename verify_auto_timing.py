"""Compare installed model inference time for manual Japanese and auto detect."""

import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg

root = Path(__file__).resolve().parent
source = root / "test-download" / "bilibili-audio-test.m4a"
clip = root / "test-download" / "auto-timing-20s.m4a"
if not clip.is_file():
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                    "-ss", "120", "-t", "20", "-i", str(source), "-c", "copy", str(clip)], check=True)
for language in ("ja", "auto"):
    output = root / "test-download" / f"auto-timing-{language}.json"
    start = time.perf_counter()
    result = subprocess.run([sys.executable, str(root / "transcribe_job.py"),
                             str(clip), str(output), str(root / "models"), language],
                            capture_output=True, text=True, timeout=180)
    print(language, "seconds", round(time.perf_counter() - start, 2), "code", result.returncode,
          "summary", result.stdout[-200:], "error", result.stderr[-300:], flush=True)
