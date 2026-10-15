"""Time the frozen automatic language path on an isolated short clip."""

import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent
exe = root / "dist-update-stage" / "每日日语" / "每日日语.exe"
if len(sys.argv) > 1:
    exe = Path(sys.argv[1]).resolve()
clip = root / "test-download" / "auto-timing-20s.m4a"
output = root / "test-download" / ("packaged-auto-final.json" if len(sys.argv) > 1 else "packaged-auto.json")
models = exe.parent / "_internal" / "models"
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = subprocess.SW_HIDE
start = time.perf_counter()
process = subprocess.Popen([str(exe), "--transcribe-job", str(clip), str(output),
                            str(models), "auto"], cwd=str(root), startupinfo=startup,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    stdout, stderr = process.communicate(timeout=180)
    code = process.returncode
finally:
    if process.poll() is None:
        process.kill()
        process.wait()
print("seconds", round(time.perf_counter() - start, 2), "code", code,
      "output_exists", output.is_file(), "stdout", stdout[-300:], "stderr", stderr[-1000:], flush=True)
raise SystemExit(0 if code == 0 and output.is_file() else 2)
