"""Inspect and download single Bilibili videos and public Xiaoyuzhou episodes."""

from __future__ import annotations

import re
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Property, QThread, QUrl, Signal, Slot

from model_settings import read_settings


def allowed_url(value: str) -> bool:
    url = urlparse(value.strip())
    return url.scheme == "https" and (url.hostname in {
        "www.bilibili.com", "bilibili.com", "m.bilibili.com", "b23.tv",
    } or is_xiaoyuzhou_url(value))


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
    with urlopen(request, timeout=20) as response:
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

    def __init__(self, url: str, mode: str, option: dict | None = None, name: str = "") -> None:
        super().__init__()
        self.url, self.mode, self.option, self.name = url, mode, option, name
        self.cancel_requested = False

    def _progress(self, value: dict) -> None:
        if self.cancel_requested:
            raise RuntimeError("下载已取消")
        if value.get("status") == "downloading":
            total = value.get("total_bytes") or value.get("total_bytes_estimate")
            if total:
                self.progressChanged.emit(min(0.99, value.get("downloaded_bytes", 0) / total))

    def run(self) -> None:
        try:
            episode = inspect_xiaoyuzhou(self.url) if is_xiaoyuzhou_url(self.url) else None
            if self.cancel_requested:
                raise RuntimeError("下载已取消")
            common = {"quiet": True, "no_warnings": True, "noplaylist": True,
                      "skip_download": self.mode == "inspect", "socket_timeout": 20}
            if self.mode == "inspect":
                if episode:
                    self.inspected.emit(episode)
                    return
                import yt_dlp
                with yt_dlp.YoutubeDL(common) as client:
                    info = client.extract_info(self.url, download=False)
                if info.get("_type") in {"playlist", "multi_video"}:
                    raise ValueError("请使用单个视频或具体分 P 的链接")
                self.inspected.emit({"title": str(info.get("title") or "未命名视频"),
                                     "thumbnail": str(info.get("thumbnail") or ""),
                                     "formats": available_formats(info)})
                return
            folder = Path(read_settings()["download_dir"])
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
            with yt_dlp.YoutubeDL(options) as client:
                info = client.extract_info(episode["audio_url"] if episode else self.url, download=True)
            if episode:
                info.update(title=episode["title"], thumbnail=episode["thumbnail"])
            candidates = [path for path in folder.iterdir() if path.is_file() and path.stem == title
                          and path.suffix.lower() in {".m4a", ".mp3", ".mp4", ".webm", ".mkv"}]
            if not candidates:
                raise FileNotFoundError("下载结束，但没有找到成品文件")
            media = max(candidates, key=lambda path: path.stat().st_mtime)
            cover = ""
            thumbnail = info.get("thumbnail")
            if thumbnail:
                try:
                    request = Request(thumbnail, headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(request, timeout=15) as response:
                        image = response.read(5_000_000)
                        content_type = response.headers.get_content_type()
                    if image:
                        extension = ".webp" if content_type == "image/webp" else ".png" if content_type == "image/png" else ".jpg"
                        cover_path = folder / f"{title}.cover{extension}"
                        cover_path.write_bytes(image)
                        cover = str(cover_path)
                except (OSError, ValueError):
                    pass
            self.progressChanged.emit(1.0)
            self.completed.emit(str(media), str(info.get("title") or title), self.url, cover)
        except Exception as exc:
            self.failed.emit(str(exc))


class DownloadBridge(QObject):
    changed = Signal()
    completed = Signal(str, str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._job: DownloadJob | None = None
        self._url = ""
        self._title = ""
        self._thumbnail = ""
        self._formats: list[dict] = []
        self._status = ""
        self._progress = 0.0
        self._error = False
        self._mode = ""

    @Property(bool, notify=changed)
    def ready(self) -> bool: return bool(self._formats)

    @Property(bool, notify=changed)
    def busy(self) -> bool: return bool(self._job and self._job.isRunning())

    @Property(bool, notify=changed)
    def inspecting(self) -> bool: return self._mode == "inspect" and self.busy

    @Property(bool, notify=changed)
    def downloading(self) -> bool: return self._mode == "download" and self.busy

    @Property(str, notify=changed)
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
        job.finished.connect(self.changed.emit)
        job.start()
        self.changed.emit()

    @Slot(str)
    def inspect(self, url: str) -> None:
        if self.busy:
            return
        if not allowed_url(url):
            self._formats, self._title, self._thumbnail = [], "", ""
            self._status, self._error = "请输入 HTTPS 的 B 站视频或小宇宙公开单集链接。", True
            self.changed.emit()
            return
        self._url, self._mode = url.strip(), "inspect"
        self._formats, self._title, self._thumbnail = [], "", ""
        self._status, self._error = "正在读取音视频信息…", False
        self._launch(DownloadJob(self._url, "inspect"))

    @Slot()
    def clearPreview(self) -> None:
        if self.busy:
            return
        self._formats, self._title, self._thumbnail = [], "", ""
        self._status = ""
        self.changed.emit()

    @Slot(int, str)
    def start(self, index: int, name: str) -> None:
        if self.busy or not 0 <= index < len(self._formats):
            return
        self._mode, self._progress = "download", 0.0
        self._status, self._error = "正在下载…", False
        self._launch(DownloadJob(self._url, "download", self._formats[index], name or self._title))

    @Slot()
    def cancel(self) -> None:
        if self._job:
            self._job.cancel_requested = True

    def _inspected(self, result: dict) -> None:
        self._title = result["title"]
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
        self._url = ""
        self.changed.emit()

    def _failed(self, detail: str) -> None:
        if self._mode == "download" and "UNEXPECTED_EOF_WHILE_READING" in detail:
            self._status = "下载连接意外断开。可重试，或选择同清晰度的另一种编码。"
        else:
            self._status = f"下载失败：{detail}"
        self._error = True
        self.changed.emit()
