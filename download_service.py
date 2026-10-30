"""Inspect/download single videos with explicit per-site proxy routing."""

from __future__ import annotations

import re
import json
import base64
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen, build_opener, ProxyHandler

from PySide6.QtCore import QObject, Property, QThread, QUrl, Signal, Slot

from model_settings import read_settings
from clash_service import ClashBridge, ClashClient, PORT, validate_loopback


def is_youtube_url(value: str) -> bool:
    try:
        url = urlparse(value.strip())
        if (url.scheme != "https" or url.username or url.password or url.port is not None
                or url.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}):
            return False
        from urllib.parse import parse_qs
        if url.hostname == "youtu.be":
            video_id = url.path.strip("/")
        elif url.path == "/watch":
            video_id = parse_qs(url.query).get("v", [""])[0]
        else:
            match = re.fullmatch(r"/(?:shorts|live|embed)/([\w-]{11})/?", url.path)
            video_id = match[1] if match else ""
        return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id))
    except ValueError:
        return False


def media_opener(proxy: str = ""):
    return build_opener(ProxyHandler({"http": proxy, "https": proxy} if proxy else {}))


def deno_path() -> str:
    from core.paths import ASSETS
    candidates = [ASSETS / "deno" / "deno.exe", Path(sys.executable).parent / "deno.exe",
                  Path(sys.prefix) / "Lib" / "site-packages" / "deno" / "deno.exe"]
    try:
        import deno
        candidates += list(Path(deno.__file__).parent.rglob("deno.exe"))
    except ImportError:
        pass
    return next((str(p) for p in candidates if p.is_file()), shutil.which("deno") or "")


def is_connection_error(detail: str) -> bool:
    text = detail.lower()
    if any(s in text for s in ("sign in", "not a bot", "private video", "not available", "http error 403", "http error 429")):
        return False
    return any(s in text for s in ("timed out", "timeout", "connection reset", "connection refused",
                                  "unable to connect", "proxyerror", "remote end closed", "unexpected_eof"))


def allowed_url(value: str) -> bool:
    url = urlparse(value.strip())
    return url.scheme == "https" and (url.hostname in {
        "www.bilibili.com", "bilibili.com", "m.bilibili.com", "b23.tv",
    } or is_xiaoyuzhou_url(value) or is_youtube_url(value))


def is_xiaoyuzhou_url(value: str) -> bool:
    url = urlparse(value.strip())
    return (url.scheme == "https" and url.hostname in {"www.xiaoyuzhoufm.com", "xiaoyuzhoufm.com"}
            and not url.username and not url.password and url.netloc == url.hostname
            and bool(re.fullmatch(r"/episode/[a-fA-F0-9]{24}/?", url.path)))


class _EpisodePage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = dict(attrs).get("id") == "__NEXT_DATA__"

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def parse_xiaoyuzhou_page(page: str) -> dict:
    parser = _EpisodePage()
    parser.feed(page)
    try:
        episode = json.loads("".join(parser.parts))["props"]["pageProps"]["episode"]
        media = episode.get("media") or {}
        source = media.get("source") or {}
        audio = source.get("url") or (episode.get("enclosure") or {}).get("url")
        if source.get("mode") not in {None, "PUBLIC"} or not audio or urlparse(audio).scheme != "https":
            raise ValueError("该单集没有公开音频，仅支持免登录的公开单集。")
        return {"title": str(episode.get("title") or "小宇宙播客"),
                "thumbnail": str((episode.get("image") or {}).get("picUrl") or ""),
                "audio_url": audio,
                "formats": [{"id": "public-audio", "label": "音频 · 原始音质", "kind": "audio",
                             "sizeLabel": size_label(media.get("size")), "estimated": False}]}
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("无法读取公开单集信息；请确认链接，网页结构也可能已更新。") from exc


def inspect_xiaoyuzhou(url: str) -> dict:
    if not is_xiaoyuzhou_url(url):
        raise ValueError("请使用小宇宙公开单集的 /episode/ 链接。")
    parsed = urlparse(url)
    canonical = "https://www.xiaoyuzhoufm.com" + parsed.path
    request = Request(canonical, headers={"User-Agent": "Mozilla/5.0"})
    with media_opener().open(request, timeout=20) as response:
        page = response.read(4_000_001)
    if len(page) > 4_000_000:
        raise ValueError("单集网页过大，无法解析。")
    return parse_xiaoyuzhou_page(page.decode("utf-8"))


def safe_name(value: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:100]
    return name or "未命名视频"


def size_label(size: int | None) -> str:
    return f"约 {size / 1048576:.1f} MB" if size else "大小未知"


def video_codec_label(codec: str) -> str:
    name = codec.split(".", 1)[0].lower()
    if not name:
        return "未知编码"
    return {"avc1": "H.264", "avc3": "H.264", "hvc1": "H.265", "hev1": "H.265",
            "av01": "AV1", "vp09": "VP9", "vp9": "VP9"}.get(name, name.upper())


def available_formats(info: dict) -> list[dict]:
    raw = info.get("formats") or []
    audio = [item for item in raw if item.get("acodec") not in {None, "none"}
             and item.get("vcodec") == "none"]
    video = [item for item in raw if item.get("vcodec") not in {None, "none"}]
    best_audio = max(audio, key=lambda item: (item.get("abr") or item.get("tbr") or 0), default=None)
    choices = []
    for item in sorted(audio, key=lambda item: item.get("abr") or item.get("tbr") or 0, reverse=True):
        size = item.get("filesize") or item.get("filesize_approx")
        bitrate = round(item.get("abr") or item.get("tbr") or 0)
        choices.append({"id": item["format_id"], "label": f"音频 · {bitrate} kbps" if bitrate else "音频",
                        "kind": "audio", "sizeLabel": size_label(size), "estimated": not bool(item.get("filesize"))})
    for item in sorted(video, key=lambda item: (item.get("height") or 0, item.get("tbr") or 0), reverse=True):
        paired = best_audio if item.get("acodec") in {None, "none"} else None
        if paired is None and item.get("acodec") in {None, "none"}:
            continue
        a_size = (paired.get("filesize") or paired.get("filesize_approx")) if paired else 0
        v_size = item.get("filesize") or item.get("filesize_approx")
        total = v_size + a_size if v_size and (a_size or not paired) else None
        size_exact = bool(item.get("filesize")) and (not paired or bool(paired.get("filesize")))
        fmt = item["format_id"] + ("+" + paired["format_id"] if paired else "")
        codec = video_codec_label(item.get("vcodec") or "")
        choices.append({"id": fmt, "label": f"视频 · {item.get('height') or '?'}p · {codec}",
                        "kind": "video", "sizeLabel": size_label(total), "estimated": not size_exact})
    return choices


class DownloadJob(QThread):
    inspected = Signal(dict)
    completed = Signal(str, str, str, str)
    progressChanged = Signal(float)
    failed = Signal(str)
    message = Signal(str)

    def __init__(self, url: str, mode: str, option: dict | None = None, name: str = "", settings=None, secret="") -> None:
        super().__init__()
        self.url, self.mode, self.option, self.name = url, mode, option, name
        self.cancel_requested = False
        self.settings, self.secret = settings, secret
        self._proxy = ""
        self._controller = None
        self._candidates = []

    def _check_cancel(self):
        if self.cancel_requested:
            raise RuntimeError("下载已取消")

    def _extract(self, options, url, download):
        import yt_dlp
        tried = set()
        if self._controller:
            tried.add(self._controller.proxies().get("Jujian-YouTube", {}).get("now"))
        for attempt in range(3):
            self._check_cancel()
            try:
                with yt_dlp.YoutubeDL(options) as client:
                    return client.extract_info(url, download=download)
            except Exception as exc:
                self._check_cancel()
                if not self._controller or not is_connection_error(str(exc)) or attempt >= 2:
                    raise
                if not self._candidates:
                    self.message.emit("连接超时，正在测试备用节点…")
                    rows = self._controller.measure(lambda: self.cancel_requested)
                    self._candidates = [r["name"] for r in rows if r["delay"] and r["name"] not in tried]
                if not self._candidates:
                    raise RuntimeError("没有可连接 YouTube 的备用节点，请检查 Clash 后重试。") from None
                name = self._candidates.pop(0)
                tried.add(name)
                self._controller.select(name)
                self.message.emit(f"已切换备用节点：{name}，正在重试…")

    def _cover(self, url, title=None, folder=None):
        if not url:
            return ""
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with media_opener(self._proxy).open(request, timeout=10) as response:
                content_type = response.headers.get_content_type()
                data = response.read(5_000_001)
            if not data or len(data) > 5_000_000 or content_type not in {"image/jpeg", "image/png", "image/webp"}:
                return ""
            if folder is None:
                return "data:" + content_type + ";base64," + base64.b64encode(data).decode()
            extension = {"image/webp": ".webp", "image/png": ".png"}.get(content_type, ".jpg")
            path = folder / f"{title}.cover{extension}"
            path.write_bytes(data)
            return str(path)
        except (OSError, ValueError):
            return ""

    def _progress(self, value: dict) -> None:
        if self.cancel_requested:
            raise RuntimeError("下载已取消")
        if value.get("status") == "downloading":
            total = value.get("total_bytes") or value.get("total_bytes_estimate")
            if total:
                self.progressChanged.emit(min(0.99, value.get("downloaded_bytes", 0) / total))

    def run(self) -> None:
        try:
            settings = self.settings if self.settings is not None else read_settings()
            youtube = is_youtube_url(self.url)
            runtime = ""
            if youtube:
                self._proxy = validate_loopback(settings.get("youtube_proxy", "http://127.0.0.1:7897"))
                runtime = deno_path()
                if not runtime:
                    raise ValueError("缺少 YouTube 所需的 Deno 运行时，请重新运行 setup.ps1 或更新安装包。")
                if settings.get("youtube_auto_node"):
                    self._controller = ClashClient(settings, self.secret)
                    self.message.emit("正在测试 YouTube 节点连通性…")
                    rows = self._controller.measure(lambda: self.cancel_requested,
                        lambda n, total: self.message.emit(f"正在测试 YouTube 节点 {n}/{total}…"))
                    self._candidates = [r["name"] for r in rows if r["delay"]]
                    if not self._candidates:
                        raise ValueError("没有可连接 YouTube 的节点，请在设置中检查 Clash。")
                    name = self._candidates.pop(0)
                    self._controller.select(name)
                    self._proxy = f"http://127.0.0.1:{PORT}"
                    self.message.emit(f"使用节点：{name}，正在读取音视频…")
                else:
                    # If a dedicated route exists, manual node selection must apply to downloads too.
                    try:
                        client = ClashClient(settings, self.secret)
                        if client.route_ready():
                            self._proxy = f"http://127.0.0.1:{PORT}"
                    except ValueError:
                        pass
            episode = inspect_xiaoyuzhou(self.url) if is_xiaoyuzhou_url(self.url) else None
            if self.cancel_requested:
                raise RuntimeError("下载已取消")
            common = {"quiet": True, "noprogress": True, "no_warnings": True, "noplaylist": True, "proxy": self._proxy,
                      "skip_download": self.mode == "inspect", "socket_timeout": 15,
                      "retries": 2, "fragment_retries": 2, "extractor_retries": 1,
                      "continuedl": True, "abort_on_unavailable_fragments": True}
            if runtime:
                common["js_runtimes"] = {"deno": {"path": runtime}}
            if self.mode == "inspect":
                if episode:
                    episode["thumbnail"] = self._cover(episode.get("thumbnail"))
                    self.inspected.emit(episode)
                    return
                import yt_dlp
                info = self._extract(common, self.url, False)
                if info.get("_type") in {"playlist", "multi_video"}:
                    raise ValueError("请使用单个视频或具体分 P 的链接")
                self.inspected.emit({"title": str(info.get("title") or "未命名视频"),
                                     "thumbnail": self._cover(info.get("thumbnail")),
                                     "formats": available_formats(info)})
                return
            folder = Path(settings["download_dir"])
            folder.mkdir(parents=True, exist_ok=True)
            title = safe_name(self.name)
            original_title = title
            copy_number = 2
            while any(path.stem == title or path.name.startswith(title + ".cover.")
                      for path in folder.iterdir() if path.is_file()):
                title = f"{original_title} ({copy_number})"
                copy_number += 1
            import imageio_ffmpeg
            import yt_dlp
            ffmpeg_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
            options = {**common, "skip_download": False, "format": "bestaudio/best" if episode else self.option["id"],
                       "outtmpl": str(folder / f"{title}.%(ext)s"), "overwrites": False,
                       "progress_hooks": [self._progress],
                       "ffmpeg_location": str(ffmpeg_exe),
                       "merge_output_format": "mp4" if self.option["kind"] == "video" else None}
            info = self._extract(options, episode["audio_url"] if episode else self.url, True)
            self._check_cancel()
            if episode:
                info.update(title=episode["title"], thumbnail=episode["thumbnail"])
            candidates = [path for path in folder.iterdir() if path.is_file() and path.stem == title
                          and path.suffix.lower() in {".m4a", ".mp3", ".mp4", ".webm", ".mkv"}]
            if not candidates:
                raise FileNotFoundError("下载结束，但没有找到成品文件")
            media = max(candidates, key=lambda path: path.stat().st_mtime)
            cover = self._cover(info.get("thumbnail"), title, folder)
            self._check_cancel()
            self.progressChanged.emit(1.0)
            self.completed.emit(str(media), title, self.url, cover)
        except Exception as exc:
            self.failed.emit(str(exc))


class DownloadBridge(QObject):
    changed = Signal()
    titleChanged = Signal()
    completed = Signal(str, str, str, str)

    def __init__(self, settings=None) -> None:
        super().__init__()
        if settings is None:
            from model_settings import SettingsBridge
            settings = SettingsBridge()
        self.settings = settings
        self._network = ClashBridge(settings, self)
        self._job: DownloadJob | None = None
        self._url = ""
        self._title = ""
        self._thumbnail = ""
        self._formats: list[dict] = []
        self._status = ""
        self._progress = 0.0
        self._error = False
        self._mode = ""

    @Property(QObject, constant=True)
    def network(self): return self._network

    def close(self):
        self.cancel()
        if self._job and self._job.isRunning():
            self._job.wait()
        self._network.close()

    @Property(bool, notify=changed)
    def ready(self) -> bool: return bool(self._formats)

    @Property(bool, notify=changed)
    def busy(self) -> bool: return bool(self._job and self._job.isRunning())

    @Property(bool, notify=changed)
    def inspecting(self) -> bool: return self._mode == "inspect" and self.busy

    @Property(bool, notify=changed)
    def downloading(self) -> bool: return self._mode == "download" and self.busy

    @Property(str, notify=titleChanged)
    def title(self) -> str: return self._title

    @Property(str, notify=changed)
    def thumbnailUrl(self) -> str: return self._thumbnail

    @Property("QVariantList", notify=changed)
    def formats(self) -> list[dict]: return self._formats

    @Property(str, notify=changed)
    def status(self) -> str: return self._status

    @Property(bool, notify=changed)
    def error(self) -> bool: return self._error

    @Property(float, notify=changed)
    def progress(self) -> float: return self._progress

    def _launch(self, job: DownloadJob) -> None:
        self._job = job
        job.inspected.connect(self._inspected)
        job.completed.connect(self._completed)
        job.progressChanged.connect(self._set_progress)
        job.failed.connect(self._failed)
        job.message.connect(self._message)
        job.finished.connect(self.changed.emit)
        if is_youtube_url(job.url):
            job.finished.connect(self._refresh_network)
        job.start()
        self.changed.emit()

    def _refresh_network(self):
        if not self._network.busy:
            self._network.run("refresh", "")

    @Slot(str)
    def inspect(self, url: str) -> None:
        if self.busy or self._network.busy:
            return
        if not allowed_url(url):
            self._formats, self._title, self._thumbnail = [], "", ""
            self.titleChanged.emit()
            self._status, self._error = "请输入 HTTPS 的 YouTube、B 站视频或小宇宙公开单集链接。", True
            self.changed.emit()
            return
        self._url, self._mode = url.strip(), "inspect"
        self._formats, self._title, self._thumbnail = [], "", ""
        self.titleChanged.emit()
        self._status, self._error = "正在读取音视频信息…", False
        self._launch(DownloadJob(self._url, "inspect", settings=self.settings.values.copy(), secret=self.settings.clashSecret()))

    @Slot()
    def clearPreview(self) -> None:
        if self.busy:
            return
        self._formats, self._title, self._thumbnail = [], "", ""
        self.titleChanged.emit()
        self._status = ""
        self.changed.emit()

    @Slot(int, str)
    def start(self, index: int, name: str) -> None:
        if self.busy or self._network.busy or not 0 <= index < len(self._formats):
            return
        self._mode, self._progress = "download", 0.0
        self._status, self._error = "正在下载…", False
        self._launch(DownloadJob(self._url, "download", self._formats[index], name.strip() or self._title,
                                 self.settings.values.copy(), self.settings.clashSecret()))

    def _message(self, text):
        self._status = text
        self.changed.emit()

    @Slot()
    def cancel(self) -> None:
        if self._job:
            self._job.cancel_requested = True

    def _inspected(self, result: dict) -> None:
        self._title = result["title"]
        self.titleChanged.emit()
        self._thumbnail = result["thumbnail"]
        self._formats = result["formats"]
        self._status = f"找到 {len(self._formats)} 种可用格式。" if self._formats else "未找到可下载格式。"
        self.changed.emit()

    def _set_progress(self, progress: float) -> None:
        self._progress = progress
        self.changed.emit()

    def _completed(self, path: str, title: str, url: str, cover: str) -> None:
        self._status = f"已加入资料库：{Path(path).name}"
        self._error = False
        self.completed.emit(path, title, url, cover)
        self._formats, self._title, self._thumbnail = [], "", ""
        self.titleChanged.emit()
        self._url = ""
        self.changed.emit()

    def _failed(self, detail: str) -> None:
        if "下载已取消" in detail:
            self._status, self._error = "下载已取消；可以重新下载。", False
            self.changed.emit()
            return
        if is_youtube_url(self._url) and is_connection_error(detail):
            self._status = "YouTube 代理连接失败或超时。请检查 Clash、代理端口或切换节点后重试。"
        elif self._mode == "download" and "UNEXPECTED_EOF_WHILE_READING" in detail:
            self._status = "下载连接意外断开。可重试，或选择同清晰度的另一种编码。"
        else:
            self._status = f"下载失败：{detail}"
        self._error = True
        self.changed.emit()
