"""Local study-project storage and Qt bridge for the desktop player."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
import os
import re
import copy
import time
from threading import Event
from bisect import bisect_right
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import av
from PySide6.QtCore import QObject, Property, QProcess, QThread, QUrl, Signal, Slot

from enrich_job import MODEL, TRANSLATION_MODEL, ModelResponseError, explain, translate, validate_analysis
from model_settings import read_settings
from linguistics import display_tokens


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ASSETS = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else ROOT
DATA = ROOT / "data"
PROJECTS = DATA / "projects"
LAST = DATA / "last-project.txt"
REMOVED_PROJECTS = DATA / "removed-projects"


def inspect_media(path: Path) -> tuple[bool, float]:
    with av.open(str(path)) as container:
        has_audio = any(stream.type == "audio" for stream in container.streams)
        has_video = any(stream.type == "video" for stream in container.streams)
        duration = max(0.0, (container.duration or 0) / 1_000_000)
    if not has_audio:
        raise ValueError("文件没有音轨，无法用于精听")
    return has_video, duration


def validate_segments(raw: object, duration: float, language: str = "ja") -> list[dict]:
    if not isinstance(raw, list):
        raise ValueError("字幕数据缺少 segments 列表")
    segments: list[dict] = []
    previous_end = 0.0
    for number, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {number} 句不是对象")
        start, end = float(item["start"]), float(item["end"])
        text = str(item.get("text", "")).strip()
        if not math.isfinite(start) or not math.isfinite(end) or not text or start < previous_end - 0.02 or end <= start or (duration and end > duration + 0.1):
            raise ValueError(f"第 {number} 句的文字或时间无效")
        words = []
        for word in item.get("words", []):
            if not isinstance(word, dict):
                continue
            w_start, w_end = float(word["start"]), float(word["end"])
            if math.isfinite(w_start) and math.isfinite(w_end) and start - 0.02 <= w_start <= w_end <= end + 0.02:
                words.append({"start": w_start, "end": w_end, "text": str(word.get("text", ""))})
        analysis = item.get("analysis", {})
        if not isinstance(analysis, dict) or analysis.get("source_text") != text:
            analysis = {}
        else:
            analysis = validate_analysis(analysis, text, language)
        suggestion = str(item.get("suggestion", ""))
        if language == "ja" and not item.get("reviewed") and re.search(r"(?:何|[0-9０-９一二三四五六七八九十])回", text):
            context = "".join(str(neighbor.get("text", "")) for neighbor in raw[max(0, number - 3):number + 1]
                              if isinstance(neighbor, dict))
            if re.search(r"ここ|どこ|エレベーター|階段|階|フロア", context):
                suggestion = "「回」は階数の「階」かもしれません。音声を確認して校正してください。"
        segments.append({
            "start": round(start, 3), "end": round(end, 3), "text": text,
            "translation": str(item.get("translation", "")),
            "reviewed": bool(item.get("reviewed", False)), "words": words,
            "tokens": display_tokens(text, words, language), "analysis": analysis,
            "suggestion": suggestion,
        })
        previous_end = end
    return segments


class EnrichmentThread(QThread):
    resultReceived = Signal(int, str, dict)
    failed = Signal(int, str)
    done = Signal(int, str)

    def __init__(self, jobs: list[dict]) -> None:
        super().__init__()
        self._jobs = jobs
        self._stop_requested = Event()

    def run(self) -> None:
        for job in self._jobs:
            if self._stop_requested.is_set():
                self.done.emit(2, "")
                return
            try:
                if job["task"] == "translation":
                    route = read_settings()
                    model = (route["cloud_model"] if route["translation_backend"] == "cloud"
                             else TRANSLATION_MODEL)
                    analysis = {"_task": "translation", "translation": translate(job["text"], job["language"]),
                                "translation_model": model}
                else:
                    analysis = explain(job["text"], job["language"])
            except ModelResponseError as exc:
                self.failed.emit(job["index"], str(exc))
                continue
            except (OSError, ValueError, KeyError, TimeoutError) as exc:
                self.done.emit(1, str(exc))
                return
            self.resultReceived.emit(job["index"], job["text"], analysis)
        self.done.emit(2 if self._stop_requested.is_set() else 0, "")

    def stop(self) -> None:
        self._stop_requested.set()


class SegmentationThread(QThread):
    ready = Signal(list, dict)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, segments, language):
        super().__init__()
        self.segments = copy.deepcopy(segments)
        self.language = language
        self.cancelled = Event()

    def run(self):
        from subtitle_split import split_segments
        from model_settings import read_settings
        try:
            routes = read_settings()
            segments, audit = split_segments(self.segments, self.language,
                use_model=routes["analysis_backend"] == "local",
                translate_new=routes["translation_backend"] == "local",
                progress=lambda done, total: self.progress.emit(done, total), cancelled=self.cancelled.is_set)
            self.ready.emit(segments, audit)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.failed.emit(str(exc))


class StudyBridge(QObject):
    stateChanged = Signal()
    mediaChanged = Signal()
    segmentsChanged = Signal()
    projectsChanged = Signal()
    seekRequested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        PROJECTS.mkdir(parents=True, exist_ok=True)
        self._project: dict = {}
        self._project_file: Path | None = None
        self._active_index = 0
        self._active_word = -1
        self._navigation_index = 0
        self._navigation_time = 0.0
        self._loop = False
        self._busy = False
        self._status = "打开本地音频或视频。"
        self._process: QProcess | None = None
        self._enrich_thread: EnrichmentThread | None = None
        self._enrich_total = 0
        self._enrich_done = 0
        self._enrich_failed = 0
        self._enriching = False
        self._enrich_task = "analysis"
        self._enrich_source = "本地"
        self._transcribe_language = "auto"
        self._projects: list[dict] = []
        self._split_thread = None
        self._splitting = False
        self._playback_position_ms = 0
        self.refreshProjects()

    def _project_path(self, media: Path) -> Path:
        digest = hashlib.sha256(str(media.resolve()).casefold().encode("utf-8")).hexdigest()[:20]
        return PROJECTS / f"{digest}.json"

    def _save(self) -> None:
        if not self._project_file:
            return
        temp = self._project_file.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self._project, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self._project_file)
        LAST.write_text(str(self._project_file), encoding="utf-8")

    @Property("QVariantList", notify=projectsChanged)
    def projects(self) -> list[dict]:
        return self._projects

    @Slot()
    def refreshProjects(self) -> None:
        items = []
        for path in PROJECTS.glob("*.json"):
            if path.name.endswith(".bak.json"):
                continue
            try:
                project = json.loads(path.read_text(encoding="utf-8"))
                media = Path(project["media_path"])
                duration = max(0, round(float(project.get("duration", 0)) * 1000))
                position = max(0, min(int(project.get("playback_ms", 0)), duration))
                if project.get("playback_completed"):
                    position = duration
                    state = "已听完"
                elif "playback_ms" not in project:
                    state = "未记录进度"
                elif duration and position >= duration * 0.95:
                    state = "已听完"
                elif position >= 5000:
                    state = "未听完"
                else:
                    state = "未开始"
                cover = str(project.get("cover_path", ""))
                items.append({
                    "path": str(path), "title": str(project.get("title") or media.stem),
                    "mediaPath": str(media), "available": media.is_file(),
                    "video": bool(project.get("has_video", False)),
                    "language": "英语" if project.get("language") == "en" else "日语",
                    "libraryLanguage": "英语" if project.get("library_language", project.get("language")) == "en" else "日语",
                    "favorite": bool(project.get("favorite", False)),
                    "durationMs": duration, "positionMs": position,
                    "progress": position / duration if duration else 0,
                    "state": state, "updated": path.stat().st_mtime,
                    "coverUrl": QUrl.fromLocalFile(cover).toString() if cover and Path(cover).is_file() else "",
                })
            except (OSError, ValueError, KeyError, TypeError):
                continue
        self._projects = sorted(items, key=lambda item: item["updated"], reverse=True)
        self.projectsChanged.emit()

    def _library_project(self, path: str) -> Path | None:
        project_path = Path(path)
        return project_path if project_path.parent == PROJECTS and project_path.is_file() and not project_path.is_symlink() else None

    @Slot(str)
    def toggleProjectFavorite(self, path: str) -> None:
        if self._busy or self._enriching:
            self._status = "正在处理媒体，请完成后再整理资料库。"
            self.stateChanged.emit()
            return
        project_path = self._library_project(path)
        if not project_path:
            return
        try:
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project["favorite"] = not bool(project.get("favorite", False))
            temporary = project_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(project_path)
            if project_path == self._project_file:
                self._project["favorite"] = project["favorite"]
            self._status = "已收藏媒体。" if project["favorite"] else "已取消收藏。"
            self.refreshProjects()
            self.stateChanged.emit()
        except (OSError, ValueError, TypeError) as exc:
            self._status = f"收藏操作失败：{exc}"
            self.stateChanged.emit()

    @Slot(str, str)
    def setProjectLibraryLanguage(self, path: str, language: str) -> None:
        if language not in {"ja", "en"}:
            return
        if self._busy or self._enriching:
            self._status = "正在处理媒体，请完成后再整理资料库。"
            self.stateChanged.emit()
            return
        project_path = self._library_project(path)
        if not project_path:
            return
        try:
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project["library_language"] = language
            temporary = project_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(project_path)
            if project_path == self._project_file:
                self._project["library_language"] = language
            self._status = "已归入英语。" if language == "en" else "已归入日语。"
            self.refreshProjects()
            self.stateChanged.emit()
        except (OSError, ValueError, TypeError) as exc:
            self._status = f"归类失败：{exc}"
            self.stateChanged.emit()

    @Slot(str)
    def deleteProject(self, path: str) -> None:
        if self._busy or self._enriching:
            self._status = "正在处理当前媒体，请完成后再删除项目。"
            self.stateChanged.emit()
            return
        project_path = self._library_project(path)
        if not project_path:
            self._status = "项目不存在，请刷新资料库。"
            self.stateChanged.emit()
            return
        try:
            REMOVED_PROJECTS.mkdir(parents=True, exist_ok=True)
            archived = REMOVED_PROJECTS / f"{project_path.stem}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
            project_path.replace(archived)
            if project_path == self._project_file:
                self._project_file = None
                self._project = {}
                self._active_index = 0
                self._active_word = -1
                if LAST.is_file() and LAST.read_text(encoding="utf-8").strip() == str(project_path):
                    LAST.unlink()
                self.mediaChanged.emit()
                self.segmentsChanged.emit()
            self._status = "已从资料库移除；音视频原文件保留，项目存入恢复目录。"
            self.refreshProjects()
            self.stateChanged.emit()
        except OSError as exc:
            self._status = f"移除项目失败：{exc}"
            self.stateChanged.emit()

    @Slot(str)
    def openProject(self, path: str) -> None:
        if self._busy or self._enriching:
            return
        project_path = Path(path)
        if project_path.parent != PROJECTS or not project_path.is_file():
            self._status = "项目不存在，请刷新资料库。"
            self.stateChanged.emit()
            return
        try:
            self._load_project(project_path)
        except (OSError, ValueError, KeyError, TypeError, av.error.FFmpegError) as exc:
            self._status = f"打开项目失败：{exc}"
            self.stateChanged.emit()

    @Slot(str, str, str, str)
    def registerDownloaded(self, media_path: str, title: str, source: str, cover: str) -> None:
        try:
            media = Path(media_path).resolve()
            project_path = self._project_path(media)
            if not project_path.is_file():
                has_video, duration = inspect_media(media)
                project = {
                    "schema_version": 1, "language": "ja", "title": title or media.stem,
                    "media_path": str(media), "source": source,
                    "has_video": has_video, "duration": duration, "segments": [],
                }
                if cover and Path(cover).is_file():
                    project["cover_path"] = cover
                temporary = project_path.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(project_path)
            self.refreshProjects()
            self._status = "下载已加入资料库；可稍后打开并转写。"
        except (OSError, ValueError, av.error.FFmpegError) as exc:
            self._status = f"文件已下载，但加入资料库失败：{exc}"
        self.stateChanged.emit()

    @Property(int, notify=mediaChanged)
    def resumeMs(self) -> int:
        return max(0, int(self._project.get("playback_ms", 0)))

    @Slot(int)
    def savePlayback(self, position_ms: int) -> None:
        if not self._project_file or position_ms < 0:
            return
        duration = self.durationMs
        position = max(0, min(position_ms, duration)) if duration else position_ms
        # Qt may reset position to zero when natural playback stops.
        if position == 0 and self._project.get("playback_completed"):
            return
        if abs(position - int(self._project.get("playback_ms", 0))) < 1000:
            return
        self._project["playback_ms"] = position
        self._project["playback_completed"] = bool(duration and position >= duration * 0.995)
        self._save()

    @Slot()
    def finishPlayback(self) -> None:
        if not self._project_file:
            return
        self._project["playback_ms"] = self.durationMs
        self._project["playback_completed"] = True
        self._save()
        self.refreshProjects()

    def _load_project(self, path: Path) -> None:
        project = json.loads(path.read_text(encoding="utf-8"))
        media = Path(project["media_path"])
        if not media.is_file():
            raise FileNotFoundError(f"媒体文件不存在：{media}")
        has_video, duration = inspect_media(media)
        project["has_video"] = has_video
        project["duration"] = duration
        project["language"] = project.get("language", "ja") if project.get("language") in {"ja", "en"} else "ja"
        project["segments"] = validate_segments(project.get("segments", []), duration, project["language"])
        self._transcribe_language = "auto"
        self._project = project
        self._project_file = path
        self._active_index = 0
        self._active_word = -1
        self._status = "已载入本地项目。"
        self.mediaChanged.emit()
        self.segmentsChanged.emit()
        self.stateChanged.emit()

    def _open_media_path(self, media: Path) -> None:
        media = media.resolve()
        has_video, duration = inspect_media(media)
        path = self._project_path(media)
        if path.is_file():
            self._load_project(path)
            return
        self._project = {
            "schema_version": 1,
            "language": "ja",
            "title": media.stem,
            "media_path": str(media),
            "source": "本地文件",
            "has_video": has_video,
            "duration": duration,
            "segments": [],
        }
        self._project_file = path
        self._transcribe_language = "auto"
        self._active_index = 0
        self._active_word = -1
        self._save()
        self._status = "已打开媒体；可转写或导入字幕。"
        self.mediaChanged.emit()
        self.segmentsChanged.emit()
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def title(self) -> str:
        return str(self._project.get("title", "尚未导入素材"))

    @Property(str, notify=stateChanged)
    def sourceLabel(self) -> str:
        return str(self._project.get("source", "本地素材"))

    @Property(str, notify=mediaChanged)
    def mediaPath(self) -> str:
        return str(self._project.get("media_path", ""))

    @Property(str, notify=mediaChanged)
    def mediaUrl(self) -> str:
        path = self._project.get("media_path")
        return QUrl.fromLocalFile(path).toString() if path else ""

    @Property(bool, notify=mediaChanged)
    def hasVideo(self) -> bool:
        return bool(self._project.get("has_video", False))

    @Property(bool, notify=mediaChanged)
    def hasMedia(self) -> bool:
        return bool(self._project.get("media_path"))

    @Property(int, notify=mediaChanged)
    def durationMs(self) -> int:
        return round(float(self._project.get("duration", 0)) * 1000)

    @Property(int, notify=stateChanged)
    def sentenceCount(self) -> int:
        return len(self._project.get("segments", []))

    @Property("QVariantList", notify=segmentsChanged)
    def segments(self) -> list[dict]:
        return self._project.get("segments", [])

    @Property(int, notify=stateChanged)
    def activeIndex(self) -> int:
        return self._active_index

    @Property(int, notify=stateChanged)
    def activeWord(self) -> int:
        return self._active_word

    @Property("QVariantMap", notify=stateChanged)
    def currentSentence(self) -> dict:
        segments = self._project.get("segments", [])
        return segments[self._active_index] if segments else {
            "start": 0, "end": 0, "text": "导入素材，开始今天的日语精听。",
            "translation": "", "reviewed": False, "words": [], "tokens": [], "analysis": {},
        }

    @Property(bool, notify=stateChanged)
    def loopSentence(self) -> bool:
        return self._loop

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=stateChanged)
    def splitting(self) -> bool:
        return self._splitting

    @Property(bool, notify=stateChanged)
    def enriching(self) -> bool:
        return self._enriching

    @Property(str, notify=stateChanged)
    def transcriptionLanguage(self) -> str:
        return self._transcribe_language

    @Property(str, notify=stateChanged)
    def contentLanguage(self) -> str:
        return self._project.get("language", "ja")

    @Slot(str)
    def setTranscriptionLanguage(self, language: str) -> None:
        if language not in {"auto", "ja", "en"} or self._busy or self._enriching:
            return
        self._transcribe_language = language
        label = {"auto": "自动识别", "ja": "日语", "en": "英语"}[language]
        self._status = f"转写语言已选：{label}；现有字幕保持原样，重新转写后生效。"
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def status(self) -> str:
        return self._status

    @Slot(str)
    def openMedia(self, url: str) -> None:
        if self._busy or self._enriching:
            self._status = "转写进行中，请完成后再切换素材。"
            self.stateChanged.emit()
            return
        try:
            self._navigation_time = 0.0
            local = QUrl(url).toLocalFile() if url.startswith("file:") else url
            self._open_media_path(Path(local))
        except (OSError, ValueError, KeyError, av.error.FFmpegError) as exc:
            self._status = f"导入失败：{exc}"
            self.stateChanged.emit()

    @Slot(str)
    def importTranscript(self, url: str) -> None:
        if self._busy or self._enriching:
            self._status = "转写进行中，请完成后再替换字幕。"
            self.stateChanged.emit()
            return
        if not self._project_file:
            self._status = "请先导入媒体。"
            self.stateChanged.emit()
            return
        try:
            local = QUrl(url).toLocalFile() if url.startswith("file:") else url
            raw = json.loads(Path(local).read_text(encoding="utf-8"))
            language = raw.get("language", self._transcribe_language if self._transcribe_language in {"ja", "en"}
                               else self._project.get("language", "ja"))
            if language not in {"ja", "en"}:
                raise ValueError("字幕语言仅支持日语或英语")
            segments = validate_segments(raw["segments"], float(self._project["duration"]), language)
            if not segments:
                raise ValueError("字幕列表为空")
            self._backup_project()
            self._project["segments"] = segments
            self._project["language"] = language
            self._transcribe_language = language
            self._active_index = 0
            self._active_word = -1
            self._save()
            self._status = f"已导入 {len(segments)} 句字幕；请逐句校对。"
            self.segmentsChanged.emit()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._status = f"字幕导入失败：{exc}"
        self.stateChanged.emit()

    def _backup_project(self) -> None:
        if self._project_file and self._project_file.is_file():
            suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self._project_file, self._project_file.with_name(f"{self._project_file.stem}-{suffix}.bak.json"))

    @Slot(int)
    def chooseSentence(self, index: int) -> None:
        segments = self._project.get("segments", [])
        if 0 <= index < len(segments):
            self._navigation_index = index
            self._navigation_time = time.monotonic()
            self._active_index = index
            self._active_word = -1
            self.stateChanged.emit()
            self.seekRequested.emit(round(segments[index]["start"] * 1000))

    @Slot(int)
    def navigateSentence(self, direction: int) -> None:
        segments = self._project.get("segments", [])
        if not segments or direction not in (-1, 1):
            return
        recent = time.monotonic() - getattr(self, "_navigation_time", 0) < 2.0
        anchor = getattr(self, "_navigation_index", self._active_index) if recent else self._active_index
        self.chooseSentence(max(0, min(len(segments) - 1, anchor + direction)))

    @Slot(int)
    def updatePlayback(self, position_ms: int) -> None:
        self._playback_position_ms = position_ms
        segments = self._project.get("segments", [])
        if not segments:
            return
        if self._navigation_time and 0 <= self._navigation_index < len(segments):
            target = segments[self._navigation_index]
            if position_ms < target["start"] * 1000 - 400 or position_ms > target["end"] * 1000 + 400:
                self._navigation_time = 0.0
        seconds = position_ms / 1000
        index = max(0, min(len(segments) - 1, bisect_right([s["start"] for s in segments], seconds) - 1))
        words = segments[index].get("words", [])
        word = next((i for i, item in enumerate(words) if item["start"] <= seconds < item["end"]), -1)
        if index != self._active_index or word != self._active_word:
            self._active_index = index
            self._active_word = word
            self.stateChanged.emit()

    @Slot()
    def toggleLoop(self) -> None:
        self._loop = not self._loop
        self.stateChanged.emit()

    @Slot(str, str, str, str, result=bool)
    def saveSentence(self, text: str, translation: str, start_text: str, end_text: str) -> bool:
        segments = self._project.get("segments", [])
        if not segments:
            return False
        try:
            start, end = float(start_text), float(end_text)
            if not math.isfinite(start) or not math.isfinite(end) or not text.strip() or start < 0 or end <= start:
                raise ValueError("原文与时间范围无效")
            if self._active_index and start < segments[self._active_index - 1]["end"] - 0.02:
                raise ValueError("起点与上一句重叠")
            if self._active_index + 1 < len(segments) and end > segments[self._active_index + 1]["start"] + 0.02:
                raise ValueError("终点与下一句重叠")
            if end > float(self._project["duration"]) + 0.1:
                raise ValueError("终点超出媒体时长")
            segment = segments[self._active_index]
            old_text = segment["text"]
            old_machine_translation = segment.get("analysis", {}).get("translation", "")
            saved_translation = translation.strip()
            if (text.strip() != old_text and not segment.get("translation")
                    and saved_translation == old_machine_translation):
                saved_translation = ""
            if segment["text"] != text.strip() or segment["start"] != start or segment["end"] != end:
                segment["words"] = []  # Existing word alignment is no longer valid.
            segment.update({
                "text": text.strip(), "translation": saved_translation,
                "start": round(start, 3), "end": round(end, 3), "reviewed": True,
            })
            if segment.get("analysis", {}).get("source_text") != segment["text"]:
                segment["analysis"] = {}
            segment["tokens"] = display_tokens(segment["text"], segment["words"], self._project.get("language", "ja"))
            self._save()
            self._status = "本句已校对并保存。"
            self.segmentsChanged.emit()
            saved = True
        except ValueError as exc:
            self._status = f"无法保存：{exc}"
            saved = False
        self.stateChanged.emit()
        return saved

    @Slot(str, str, result=bool)
    def saveAnalysis(self, grammar: str, vocabulary_text: str) -> bool:
        segments = self._project.get("segments", [])
        if not segments or self._enriching:
            return False
        segment = segments[self._active_index]
        vocabulary = []
        for line in vocabulary_text.splitlines():
            if not line.strip():
                continue
            separator = "：" if "：" in line else ":"
            if separator not in line:
                self._status = "词汇格式应为：原文词：中文意思。"
                self.stateChanged.emit()
                return False
            surface, meaning = (part.strip() for part in line.split(separator, 1))
            if not surface or surface not in segment["text"] or not meaning:
                self._status = "词汇必须来自本句原文，并填写中文意思。"
                self.stateChanged.emit()
                return False
            vocabulary.append({"surface": surface, "meaning": meaning})
        previous_analysis = segment.get("analysis", {})
        segment["analysis"] = {
            "grammar": grammar.strip()[:140], "vocabulary": vocabulary[:4],
            "model": "manual", "source_text": segment["text"],
            "translation": previous_analysis.get("translation", ""),
            "translation_model": previous_analysis.get("translation_model", ""),
        }
        self._save()
        self._status = "本句解析已保存。"
        self.segmentsChanged.emit()
        self.stateChanged.emit()
        return True

    @Slot()
    def transcribe(self) -> None:
        if self._busy or self._enriching or not self._project_file:
            return
        output = DATA / "transcription-pending.json"
        if output.exists():
            output.unlink()
        if getattr(sys, "frozen", False):
            model_root = ASSETS / "models"
        else:
            model_root = ROOT / "models"
        self._process = QProcess(self)
        self._process.setProgram(sys.executable)
        job_args = [self._project["media_path"], str(output), str(model_root), self._transcribe_language]
        self._process.setArguments(
            ["--transcribe-job", *job_args] if getattr(sys, "frozen", False)
            else [str(ROOT / "transcribe_job.py"), *job_args]
        )
        self._process.setWorkingDirectory(str(ROOT))
        self._process.finished.connect(lambda code, status: self._finish_transcription(code, output))
        self._process.errorOccurred.connect(lambda error: self._process_error(str(error)))
        self._busy = True
        self._status = "正在本地转写整段媒体；播放仍可正常使用。"
        self.stateChanged.emit()
        self._process.start()

    def _process_error(self, error: str) -> None:
        self._busy = False
        self._status = f"转写进程启动失败：{error}"
        self.stateChanged.emit()

    def _finish_transcription(self, code: int, output: Path) -> None:
        self._busy = False
        try:
            if code != 0:
                detail = bytes(self._process.readAllStandardError()).decode("utf-8", "replace")[-400:] if self._process else ""
                raise RuntimeError(detail or f"退出码 {code}")
            raw = json.loads(output.read_text(encoding="utf-8"))
            language = raw.get("language", "ja")
            if language not in {"ja", "en"}:
                raise ValueError(f"自动识别到 {language}；当前精听卡片只支持日语或英语，请手动选择后重试")
            segments = validate_segments(raw["segments"], float(self._project["duration"]), language)
            if not segments:
                raise ValueError("转写没有得到句子")
            self._backup_project()
            self._project["segments"] = segments
            self._project["language"] = language
            self._active_index = 0
            self._active_word = -1
            self._save()
            self._status = f"转写完成：识别为{'英语' if language == 'en' else '日语'}，共 {len(segments)} 句。请逐句校对。"
            self.segmentsChanged.emit()
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self._status = f"转写失败，原字幕已保留：{exc}"
        self.stateChanged.emit()

    @Slot(bool)
    def startEnrichment(self, all_sentences: bool) -> None:
        self._start_model_jobs(all_sentences, "analysis")

    @Slot(bool)
    def startTranslation(self, all_sentences: bool) -> None:
        self._start_model_jobs(all_sentences, "translation")

    def _start_model_jobs(self, all_sentences: bool, task: str) -> None:
        if (self._busy or self._enriching or not self._project_file
                or self._enrich_thread and self._enrich_thread.isRunning()):
            return
        segments = self._project.get("segments", [])
        selected = list(enumerate(segments)) if all_sentences else (
            [(self._active_index, segments[self._active_index])] if segments else [])
        jobs = []
        for i, segment in selected:
            analysis = segment.get("analysis", {})
            if task == "translation":
                needed = not segment.get("translation") and (not all_sentences or not analysis.get("translation"))
            else:
                needed = analysis.get("model") != "manual" and (
                    not all_sentences or (not analysis.get("grammar") and not analysis.get("vocabulary")))
            if needed:
                jobs.append({"index": i, "text": segment["text"], "task": task,
                             "language": self._project.get("language", "ja")})
        if not jobs:
            self._status = "没有需要解析的句子。"
            self.stateChanged.emit()
            return
        self._enrich_thread = EnrichmentThread(jobs)
        self._enrich_thread.resultReceived.connect(self._read_enrichment)
        self._enrich_thread.failed.connect(self._fail_enrichment)
        self._enrich_thread.done.connect(self._finish_enrichment)
        self._enrich_total = len(jobs)
        self._enrich_done = 0
        self._enrich_failed = 0
        self._enriching = True
        self._enrich_task = task
        route = read_settings()
        self._enrich_source = "云端" if route[f"{task}_backend"] == "cloud" else "本地"
        model = route["cloud_model"] if self._enrich_source == "云端" else MODEL
        self._status = f"{self._enrich_source}模型 {model}：准备{'翻译' if task == 'translation' else '解析'} {len(jobs)} 句。"
        self.stateChanged.emit()
        self._enrich_thread.start()

    def _read_enrichment(self, index: int, text: str, analysis: dict) -> None:
        try:
            segments = self._project.get("segments", [])
            if not 0 <= index < len(segments) or segments[index]["text"] != text:
                return
            previous = segments[index].get("analysis", {})
            if analysis.get("_task") == "translation":
                if segments[index].get("translation"):
                    return
                segments[index]["analysis"] = validate_analysis({
                    **previous, "translation": analysis["translation"],
                    "translation_model": analysis["translation_model"], "source_text": text,
                }, text, self._project.get("language", "ja"))
            else:
                if previous.get("model") == "manual":
                    return
                validated = validate_analysis({
                    **analysis, "translation": previous.get("translation", ""),
                    "translation_model": previous.get("translation_model", ""),
                }, text, self._project.get("language", "ja"))
                validated["model"] = analysis.get("model") or MODEL
                segments[index]["analysis"] = validated
            self._enrich_done += 1
            self._save()
            self.segmentsChanged.emit()
            action = "翻译" if self._enrich_task == "translation" else "解析"
            self._status = f"{self._enrich_source}{action} {self._enrich_done} / {self._enrich_total} 句；生成内容待校对。"
            self.stateChanged.emit()
        except (UnicodeError, ValueError, KeyError, TypeError):
            pass

    def _fail_enrichment(self, index: int, detail: str) -> None:
        self._enrich_failed += 1
        self._status = f"第 {index + 1} 句处理失败：{detail}；已跳过，稍后可重试。"
        self.stateChanged.emit()

    def _finish_enrichment(self, code: int, detail: str) -> None:
        self._enriching = False
        action = "翻译" if self._enrich_task == "translation" else "解析"
        if code == 0:
            self._status = (f"{self._enrich_source}{action}完成 {self._enrich_done} 句，跳过 {self._enrich_failed} 句；"
                            "未完成的句子可再次处理，请校对生成的内容。")
        elif code == 2:
            self._status = f"{self._enrich_source}{action}已停止，已保存 {self._enrich_done} 句，跳过 {self._enrich_failed} 句。"
        else:
            self._status = f"{self._enrich_source}{action}中断：{detail}；已保存 {self._enrich_done} 句。"
        self.stateChanged.emit()

    @Slot()
    def stopEnrichment(self) -> None:
        if self._enrich_thread and self._enriching:
            self._enrich_thread.stop()
            self._status = "正在等待当前句解析完成后停止。"
            self.stateChanged.emit()

    def close(self) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(3000)
        if self._enrich_thread and self._enrich_thread.isRunning():
            self._enrich_thread.stop()
            self._enrich_thread.wait()
        if self._split_thread and self._split_thread.isRunning():
            self._split_thread.cancelled.set()
            self._split_thread.wait()

    @Slot()
    def organizeSubtitles(self) -> None:
        if self._busy or self._enriching or not self._project_file or (self._split_thread and self._split_thread.isRunning()):
            return
        language = self._project.get("language")
        if language not in {"ja", "en"}:
            self._status = "字幕整理需要日语或英语的逐词时间戳。"
            self.stateChanged.emit()
            return
        self._splitting = self._busy = True
        self._split_source = copy.deepcopy(self._project.get("segments", []))
        self._split_thread = SegmentationThread(self._split_source, language)
        self._split_thread.progress.connect(self._split_progress)
        self._split_thread.ready.connect(self._split_ready)
        self._split_thread.failed.connect(self._split_failed)
        self._status = ("正在按句末和停顿整理日语字幕；新拆分句子的译文可稍后重新翻译。" if language == "ja" else
                        "正在整理字幕；本地后端可辅助分段和翻译，云端后端可在整理后点击中文翻译。")
        self.stateChanged.emit()
        self._split_thread.start()

    def _split_progress(self, done, total):
        self._status = f"正在本地整理字幕：已生成 {done} 个短片段。"
        self.stateChanged.emit()

    def _split_failed(self, message):
        self._busy = self._splitting = False
        self._status = f"字幕整理未完成，原字幕已保留：{message}"
        self.stateChanged.emit()

    def _split_ready(self, segments, audit):
        original_project = copy.deepcopy(self._project)
        try:
            if self._project.get("segments", []) != self._split_source:
                raise ValueError("字幕在处理期间已改变，请重新整理")
            if audit.get("changed"):
                validated = validate_segments(segments, float(self._project["duration"]), self._project.get("language", "ja"))
                backup = DATA / "subtitle-backups" / f"{self._project_file.stem}-{datetime.now():%Y%m%d-%H%M%S}.json"
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_text(json.dumps(self._project, ensure_ascii=False, indent=2), encoding="utf-8")
                self._project["segments"] = validated
                self._project["listening_segmentation"] = {"version": 1, "audit": audit, "backup": str(backup)}
                self._active_index = 0
                self._active_word = -1
                self.updatePlayback(self._playback_position_ms)
                self._save()
                self.segmentsChanged.emit()
            self._status = f"字幕整理完成：{audit.get('original_count', len(segments))} → {len(segments)} 个片段；原字幕已备份，译文请校对。"
            if audit.get("fallback_groups") or audit.get("translation_failures"):
                self._status += " 部分模型请求未完成，已用规则分段；缺失译文可稍后翻译。"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._project = original_project
            self._status = f"字幕整理失败，原字幕已保留：{exc}"
        finally:
            self._busy = self._splitting = False
            self.stateChanged.emit()
