"""Opt-in source/frozen YouTube integration check with isolated data and media."""
def main():
    import json
    import os
    import sys
    import tempfile
    import traceback
    from pathlib import Path
    output = Path(os.environ.get("JUJIAN_CHECK_OUTPUT", "release-verification/youtube-check"))
    output.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = (output / "youtube-check.log").open("w", encoding="utf-8")
        sys.stderr = sys.stdout
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = {"passed": False, "failures": []}
    with tempfile.TemporaryDirectory(prefix="jujian-youtube-check-") as folder:
        os.environ["JUJIAN_DATA_DIR"] = folder
        try:
            from PySide6.QtCore import QCoreApplication
            app = QCoreApplication([])
            from model_settings import DEFAULTS
            from clash_service import ClashClient
            from download_service import DownloadJob, deno_path
            import av
            import yt_dlp_ejs
            runtime = Path(deno_path())
            assert runtime.is_file(), "Deno executable missing"
            client = ClashClient(DEFAULTS)
            before = client.request("/configs")
            assert client.route_ready(), "Dedicated Clash download route not ready"
            settings = {**DEFAULTS, "download_dir": folder, "youtube_auto_node": True}
            inspection = DownloadJob("https://www.youtube.com/watch?v=jNQXAC9IVRw", "inspect", settings=settings)
            metadata, failures = [], []
            inspection.inspected.connect(metadata.append)
            inspection.failed.connect(failures.append)
            inspection.run()
            assert metadata and not failures, failures
            info = metadata[0]
            choices = [f for f in info["formats"] if f["kind"] == "video" and "H.264" in f["label"]]
            assert choices, "No compatible video/audio format"
            settings["youtube_auto_node"] = False  # reuse the node selected by the inspection
            job = DownloadJob(inspection.url, "download", choices[-1], "youtube-package-check", settings)
            completed = []
            job.completed.connect(lambda *args: completed.append(args))
            job.failed.connect(failures.append)
            job.run()
            assert completed and not failures, failures
            media = Path(completed[0][0])
            with av.open(str(media)) as container:
                assert container.streams.video and container.streams.audio
                duration = float(container.duration / av.time_base)
                assert duration > 18
            assert Path(completed[0][3]).is_file(), "Cover image missing"
            after = client.request("/configs")
            assert before["tun"] == after["tun"], "TUN configuration changed"
            assert before["mode"] == after["mode"], "Clash mode changed"
            result.update(passed=True, formats=len(info["formats"]), video_bytes=media.stat().st_size,
                          duration_seconds=duration, cover=True, deno=str(runtime),
                          tun_unchanged=True, tun_enabled=after["tun"].get("enable"))
        except Exception:
            result["failures"].append(traceback.format_exc())
    (output / "youtube-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1
