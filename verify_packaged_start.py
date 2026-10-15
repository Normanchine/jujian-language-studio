"""Bounded packaged GUI launch check without modifying installed user data."""

import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent
exe = root / "dist-update-stage" / "每日日语" / "每日日语.exe"
if len(sys.argv) > 1:
    exe = Path(sys.argv[1]).resolve()
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = subprocess.SW_HIDE
process = subprocess.Popen([str(exe)], cwd=str(exe.parent), startupinfo=startup,
                           creationflags=subprocess.CREATE_NO_WINDOW)
for second in range(30):
    if process.poll() is not None:
        break
    if second >= 10 and (exe.parent / "data" / "projects").is_dir():
        break
    time.sleep(1)
code = process.poll()
ready = (exe.parent / "data" / "projects").is_dir()
print("packaged_gui_alive", code is None, "initialized", ready,
      "pid", process.pid, "exit_code", code, flush=True)
if code is None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
raise SystemExit(0 if code is None and ready else 2)
