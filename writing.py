"""Writing drafts, AI feedback snapshots, and independent study notes."""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from ai_client import ask_json
from review_guidance import review_english

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ESSAYS = ROOT / "data" / "essays"
NOTES = ROOT / "data" / "notes"
FAVORITES = ROOT / "data" / "writing-favorites.json"
TOKEN_RE = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]", re.UNICODE)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def tokens_for(text: str) -> list[dict]:
    return [{"id": index, "text": match.group(), "start": match.start(), "end": match.end()}
            for index, match in enumerate(TOKEN_RE.finditer(text), start=1)]


def validate_marks(text: str, raw: object) -> tuple[list[dict], list[str]]:
    tokens = tokens_for(text)
    marks, unanchored = [], []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", ""))
        correction = str(item.get("correction", "")).strip()[:300]
        reason = str(item.get("reason", "")).strip()[:500]
        if not reason:
            continue
        if correction and correction.casefold() == quote.strip().casefold():
            continue
        if any(phrase in reason for phrase in ("无需修改", "无需更改", "正确，无需", "没有错误")):
            continue
        try:
            first, last = int(item["start_token"]), int(item["end_token"])
            if not (1 <= first <= last <= len(tokens)):
                raise ValueError("token out of range")
            lower, upper = tokens[first - 1]["start"], tokens[last - 1]["end"]
            start = lower + int(item.get("start_char", 0))
            end = tokens[last - 1]["start"] + int(item.get("end_char", len(tokens[last - 1]["text"])))
            if not quote and correction and lower <= start == end <= upper:
                pass  # An insertion is anchored at a token character boundary.
            elif not (lower <= start <= end <= upper and text[start:end] == quote and quote):
                # Models often count characters from the whole sentence. The quote itself
                # can recover a unique position inside the numbered token range.
                if not quote or text[lower:upper].count(quote) != 1:
                    raise ValueError("quoted text mismatch")
                start = text.find(quote, lower, upper)
                end = start + len(quote)
            marks.append({"start": start, "end": end, "quote": quote,
                          "correction": correction, "reason": reason,
                          "kind": "error" if item.get("kind") == "error" else "style"})
        except (KeyError, TypeError, ValueError, IndexError):
            if quote and text.count(quote) == 1:
                start = text.index(quote)
                marks.append({"start": start, "end": start + len(quote), "quote": quote,
                              "correction": correction, "reason": reason,
                              "kind": "error" if item.get("kind") == "error" else "style"})
            else:
                unanchored.append(f"{quote or '未定位的表达'}：{reason}")
    return marks[:60], unanchored[:20]


def review_html(text: str, marks: list[dict]) -> str:
    """Render a read-only teacher-marked sheet; no AI text is injected as HTML."""
    segments = []
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if not content:
            segments.append("<div class='paragraph-gap'></div>")
        for match in re.finditer(r"[^.!?。！？]+[.!?。！？]*", content):
            start, end = offset + match.start(), offset + match.end()
            local = [mark for mark in marks if start <= mark["start"] < end and mark["end"] <= end]
            pieces = []
            cursor = start
            for mark in sorted(local, key=lambda value: (value["start"], value["end"])):
                if mark["start"] < cursor:
                    continue
                pieces.append(html.escape(text[cursor:mark["start"]]))
                cls = "error" if mark["kind"] == "error" else "style"
                pieces.append(f"<span class='{cls}'>{html.escape(text[mark['start']:mark['end']])}</span>")
                cursor = mark["end"]
            pieces.append(html.escape(text[cursor:end]))
            notes = "".join(
                "<div class='annotation'><span class='arrow'>↳</span>"
                + (f"<strong>{html.escape(mark['correction'])}</strong> · " if mark["correction"] else "")
                + html.escape(mark["reason"]) + "</div>" for mark in local)
            segments.append("<div class='sentence'>" + "".join(pieces) + notes + "</div>")
        offset += len(line)
    if not text:
        segments.append("<div class='sentence'>没有可批改的正文。</div>")
    css = """
    html{background:#f5f6f4;color:#26342c;font-family:'Segoe UI','Microsoft YaHei UI',sans-serif}
    body{max-width:780px;margin:26px auto;padding:32px 42px 54px;background:white;border:1px solid #e4e8e3;border-radius:10px;line-height:1.8}
    .sentence{font-size:17px;white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 18px}
    .paragraph-gap{height:14px}.error{background:#ffe9ed;color:#ad354a;text-decoration:underline wavy #c94859 2px;text-underline-offset:4px}
    .style{background:#fff0db;text-decoration:underline dotted #d58b33 2px;text-underline-offset:4px}
    .annotation{max-width:690px;box-sizing:border-box;margin:9px 0 3px 12px;padding:8px 12px;border-left:3px solid #c94859;background:#fff6f7;border-radius:0 7px 7px 0;color:#6b3942;font-size:13px;line-height:1.55;white-space:normal}
    .arrow{padding-right:8px;color:#c94859}.annotation strong{color:#a62d43}
    """
    return "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>" + "".join(segments) + "</body></html>"


def review_blocks(text: str, marks: list[dict]) -> list[dict]:
    """Give Qt a sentence and its notes without changing the saved original."""
    blocks = []
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if not content:
            blocks.append({"html": "", "notes": [], "gap": True})
        for match in re.finditer(r"[^.!?。！？]+[.!?。！？]*", content):
            start, end = offset + match.start(), offset + match.end()
            local = [mark for mark in marks if start <= mark["start"] < end and mark["end"] <= end]
            parts, cursor = [], start
            for mark in sorted(local, key=lambda value: (value["start"], value["end"])):
                if mark["start"] < cursor:
                    continue
                parts.append(html.escape(text[cursor:mark["start"]]))
                color = "#AB3549" if mark["kind"] == "error" else "#A26A28"
                background = "#FFE9ED" if mark["kind"] == "error" else "#FFF0DB"
                shown = text[mark["start"]:mark["end"]] or "＋"
                parts.append(f'<span style="color:{color};background-color:{background};text-decoration:underline">'
                             + html.escape(shown) + "</span>")
                cursor = mark["end"]
            parts.append(html.escape(text[cursor:end]))
            blocks.append({"html": "".join(parts), "gap": False,
                           "notes": [{"quote": mark["quote"], "correction": mark["correction"], "reason": mark["reason"],
                                      "kind": mark["kind"]} for mark in local]})
        offset += len(line)
    return blocks or [{"html": "", "notes": [], "gap": False}]


class WritingJob(QThread):
    resultReady = Signal(str, dict)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, mode: str, draft: dict, level: str = "") -> None:
        super().__init__()
        self.mode, self.draft, self.level = mode, draft, level

    def run(self) -> None:
        try:
            language = self.draft.get("language", "ja")
            if self.mode == "topic":
                mode = self.draft.get("writing_mode", "practice")
                task = {"toefl_email": "TOEFL Write an Email 风格的邮件写作",
                        "toefl_discussion": "TOEFL Academic Discussion 风格的学术讨论"}.get(mode, "自由作文")
                prompt = (f"请为{'日语' if language == 'ja' else '英语'}学习者出一道{task}练习题。"
                          "只输出 JSON 对象，字段 topic（简洁、明确的题目，中文说明）。"
                          "不要声称为官方真题或给出官方分数。")
                result = ask_json(prompt, "writing", 300)
                topic = str(result.get("topic", "")).strip()[:400]
                if not topic:
                    raise ValueError("模型没有返回题目")
                self.resultReady.emit("topic", {"topic": topic})
                return
            if self.mode == "custom_vocabulary":
                terms = [part.strip() for part in re.split(r"[,，;；\n]+", self.level) if part.strip()][:20]
                prompt = (f"为{'日语' if language == 'ja' else '英语'}学习者制作词汇卡。"
                          "严格只处理给定词，不要添加新词。每项返回 expression、meaning(准确中文释义)、"
                          "example(自然的原语言例句，展示用法)。只返回 JSON 对象 items 数组。词汇：" + json.dumps(terms, ensure_ascii=False))
                result = ask_json(prompt, "writing", 1600)
                allowed = {term.casefold(): term for term in terms}
                items = []
                for item in result.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    key = str(item.get("expression", "")).strip().casefold()
                    if key in allowed and item.get("meaning") and item.get("example"):
                        items.append({"expression": allowed.pop(key), "kind": "vocabulary",
                                      "meaning": str(item["meaning"])[:200], "example": str(item["example"])[:300]})
                if not items:
                    raise ValueError("模型没有返回可用的词汇卡")
                self.resultReady.emit("custom_materials", {"items": items})
                return
            if self.mode == "materials":
                if language == "ja":
                    prompt = ("请给日语写作学习者生成 15 个可选写作素材，难度为" + self.level
                              + "。包含语法表达为主，少量实用词汇。每项给 expression、kind(grammar/vocabulary)、meaning(中文)、example(日语例句)。"
                              "避免重复，不能声称等级是 JLPT 官方清单。只返回 JSON：{\"items\":[...]}。主题：" + self.draft.get("topic", "自由写作"))
                else:
                    prompt = ("请给英语写作学习者生成 15 个可选写作素材，偏学术表达和托福风格，难度" + self.level
                              + "。包含有用词汇与句式，每项给 expression、kind(grammar/vocabulary)、meaning(中文)、example(英文例句)。"
                              "避免生僻堆砌。只返回 JSON：{\"items\":[...]}。主题：" + self.draft.get("topic", "自由写作"))
                result = ask_json(prompt, "writing", 2300)
                items = []
                for item in result.get("items", [])[:20]:
                    if isinstance(item, dict) and item.get("expression"):
                        items.append({key: str(item.get(key, ""))[:200]
                                      for key in ("expression", "kind", "meaning", "example")})
                if not items:
                    raise ValueError("模型未给出可用的写作素材")
                self.resultReady.emit("materials", {"items": items})
                return
            text = str(self.draft.get("text", ""))
            if not text.strip():
                raise ValueError("请先写正文")
            targets = self.draft.get("targets", [])
            if language == "en":
                review = review_english(self.draft)
                review["created"] = now()
                self.progress.emit(1, 1)
            else:
                prompt = ("你是日语写作指导老师。给中文母语者的作文指出具体语法、用词、自然度与结构问题，"
                          "特别检查本次目标表达是否自然。不要称为 JLPT 作文考试或官方评分。"
                          "只返回 JSON 对象，字段 overall、specific_advice(数组，每项含 quote、suggestion、reason)、target_feedback，均用中文说明。\n"
                          f"题目：{self.draft.get('topic','')}\n本次目标：{targets}\n作文：\n{text}")
                result = ask_json(prompt, "writing", 2200)
                self.progress.emit(1, 1)
                advice = []
                for item in result.get("specific_advice", [])[:20]:
                    if isinstance(item, dict):
                        advice.append({key: str(item.get(key, ""))[:500]
                                       for key in ("quote", "suggestion", "reason")})
                review = {"language": "ja", "text": text, "created": now(), "advice": advice,
                          "overall": str(result.get("overall", ""))[:2000],
                          "targetFeedback": str(result.get("target_feedback", ""))[:1000]}
            self.resultReady.emit("review", review)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.failed.emit(str(exc))


class WritingBridge(QObject):
    changed = Signal()
    draftsChanged = Signal()
    notesChanged = Signal()
    reviewReady = Signal()
    topicReady = Signal()

    def __init__(self) -> None:
        super().__init__()
        ESSAYS.mkdir(parents=True, exist_ok=True)
        NOTES.mkdir(parents=True, exist_ok=True)
        self._draft: dict = {}
        self._file: Path | None = None
        self._drafts: list[dict] = []
        self._notes: list[dict] = []
        self._materials: list[dict] = []
        try:
            saved_favorites = json.loads(FAVORITES.read_text(encoding="utf-8"))
            self._favorites = saved_favorites.get("items", []) if isinstance(saved_favorites, dict) else []
        except (OSError, ValueError):
            self._favorites = []
        self._job: WritingJob | None = None
        self._job_file: Path | None = None
        self._status = ""
        self.refresh()

    @Property("QVariantList", notify=draftsChanged)
    def drafts(self) -> list[dict]: return self._drafts

    @Property("QVariantList", notify=notesChanged)
    def notes(self) -> list[dict]: return self._notes

    @Property("QVariantMap", notify=changed)
    def current(self) -> dict: return self._draft

    @Property(str, notify=changed)
    def currentPath(self) -> str: return str(self._file) if self._file else ""

    @Property("QVariantList", notify=changed)
    def materials(self) -> list[dict]: return self._materials

    @Property("QVariantList", notify=changed)
    def favorites(self) -> list[dict]: return self._favorites

    @Property(str, notify=changed)
    def status(self) -> str: return self._status

    @Property(bool, notify=changed)
    def busy(self) -> bool: return bool(self._job and self._job.isRunning())

    @Property("QVariantList", notify=changed)
    def reviewBlocks(self) -> list[dict]:
        review = self._draft.get("review", {})
        if review.get("language") != "en":
            return []
        return review_blocks(review.get("text", ""), review.get("marks", []))

    @Slot()
    def refresh(self) -> None:
        drafts = []
        for path in ESSAYS.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                drafts.append({"path": str(path), "title": data.get("title") or "未命名作文",
                               "language": data.get("language", "ja"), "updated": data.get("updated", ""),
                               "updatedLabel": str(data.get("updated", ""))[:10],
                                "preview": str(data.get("text", "")).strip().replace("\n", " ")[:90],
                                "reviewed": bool(data.get("review")),
                                "favorite": bool(data.get("favorite", False))})
            except (OSError, ValueError):
                continue
        self._drafts = sorted(drafts, key=lambda item: item["updated"], reverse=True)
        self.draftsChanged.emit()
        notes = []
        for path in NOTES.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                notes.append({"path": str(path), **data})
            except (OSError, ValueError):
                continue
        self._notes = sorted(notes, key=lambda item: item.get("updated", ""), reverse=True)
        self.notesChanged.emit()

    @Slot(str)
    def newDraft(self, language: str) -> None:
        if language not in {"ja", "en"}:
            language = "ja"
        self._file = ESSAYS / f"{uuid4().hex}.json"
        self._draft = {"schema_version": 1, "title": "未命名作文", "language": language,
                       "topic": "", "text": "", "targets": [], "writing_mode": "practice",
                       "created": now(), "updated": now()}
        self._materials = []
        self._status = ""
        atomic_json(self._file, self._draft)
        self.refresh()
        self.changed.emit()

    @Slot(str)
    def openDraft(self, path: str) -> None:
        file = Path(path)
        if file.parent != ESSAYS or not file.is_file():
            self._status = "作文不存在。"
            self.changed.emit()
            return
        try:
            self._draft = json.loads(file.read_text(encoding="utf-8"))
            self._file = file
            self._materials = self._draft.get("materials", [])
            self._status = "已打开作文。"
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self._status = f"打开作文失败：{exc}"
            self.changed.emit()

    @Slot(str, str, str)
    def saveDraft(self, title: str, topic: str, text: str) -> None:
        if not self._file:
            return
        self._draft.update({"title": title.strip() or "未命名作文", "topic": topic.strip(),
                            "text": text, "updated": now()})
        atomic_json(self._file, self._draft)
        self.refresh()
        self.changed.emit()

    @Slot(str)
    def setTargets(self, json_text: str) -> None:
        if not self._file:
            return
        try:
            values = json.loads(json_text)
            if not isinstance(values, list):
                return
            self._draft["targets"] = list(dict.fromkeys(str(value).strip()[:100] for value in values if str(value).strip()))[:30]
            atomic_json(self._file, self._draft)
            self.changed.emit()
        except (OSError, ValueError):
            pass

    @Slot(str)
    def toggleFavorite(self, expression: str) -> None:
        language = self._draft.get("language", "ja")
        existing = next((item for item in self._favorites if item.get("expression") == expression
                         and item.get("language") == language), None)
        if existing:
            self._favorites.remove(existing)
        else:
            material = next((item for item in self._materials if item.get("expression") == expression), None)
            if not material:
                return
            self._favorites.append({**material, "language": language})
        atomic_json(FAVORITES, {"items": self._favorites})
        self.changed.emit()

    @Slot(str)
    def toggleDraftFavorite(self, path: str) -> None:
        file = Path(path)
        if file.parent != ESSAYS or not file.is_file():
            return
        data = json.loads(file.read_text(encoding="utf-8"))
        data["favorite"] = not bool(data.get("favorite", False))
        atomic_json(file, data)
        if file == self._file:
            self._draft = data
            self.changed.emit()
        self.refresh()

    @Slot(str)
    def deleteDraft(self, path: str) -> None:
        file = Path(path)
        if file.parent != ESSAYS or not file.is_file():
            return
        file.unlink()
        if file == self._file:
            self._file = None
            self._draft = {}
            self._materials = []
            self.changed.emit()
        self._status = "作文已删除。"
        self.refresh()

    @Slot(str, str)
    def addCustomMaterials(self, text: str, kind: str) -> None:
        if not self._file or self.busy:
            return
        terms = list(dict.fromkeys(part.strip() for part in re.split(r"[,，;；\n]+", text) if part.strip()))[:20]
        if not terms:
            return
        if kind == "grammar":
            existing = {item.get("expression", "").casefold() for item in self._materials}
            self._materials.extend({"expression": term, "kind": "grammar", "meaning": "", "example": ""}
                                   for term in terms if term.casefold() not in existing)
            self._draft["materials"] = self._materials
            atomic_json(self._file, self._draft)
            self._status = f"已添加 {len(terms)} 项语法卡。"
            self.changed.emit()
            return
        self._status = "正在生成词汇卡…"
        self._job = WritingJob("custom_vocabulary", dict(self._draft), "\n".join(terms))
        self._job_file = self._file
        self._job.resultReady.connect(self._ready)
        self._job.failed.connect(self._failed)
        self._job.finished.connect(self.changed.emit)
        self._job.start()
        self.changed.emit()

    @Slot(str)
    def setMode(self, mode: str) -> None:
        if not self._file or mode not in {"practice", "toefl_email", "toefl_discussion"}:
            return
        if self._draft.get("language") == "ja" and mode != "practice":
            return
        self._draft["writing_mode"] = mode
        atomic_json(self._file, self._draft)
        self.changed.emit()

    @Slot()
    def generateTopic(self) -> None:
        if self.busy or not self._file:
            return
        self._status = "正在生成写作题目…"
        self._job = WritingJob("topic", dict(self._draft))
        self._job_file = self._file
        self._job.resultReady.connect(self._ready)
        self._job.failed.connect(self._failed)
        self._job.finished.connect(self.changed.emit)
        self._job.start()
        self.changed.emit()

    @Slot(str)
    def generateMaterials(self, level: str) -> None:
        if self.busy or not self._file:
            return
        self._status = "正在生成写作素材…"
        self._job = WritingJob("materials", dict(self._draft), level)
        self._job_file = self._file
        self._job.resultReady.connect(self._ready)
        self._job.failed.connect(self._failed)
        self._job.finished.connect(self.changed.emit)
        self._job.start()
        self.changed.emit()

    @Slot()
    def review(self) -> None:
        if self.busy or not self._file:
            return
        self._status = "正在通读整篇作文并整理建议…"
        self._job = WritingJob("review", dict(self._draft))
        self._job_file = self._file
        self._job.resultReady.connect(self._ready)
        self._job.failed.connect(self._failed)
        self._job.progress.connect(self._progress)
        self._job.finished.connect(self.changed.emit)
        self._job.start()
        self.changed.emit()

    def _progress(self, completed: int, total: int) -> None:
        self._status = "正在整理批改结果…"
        self.changed.emit()

    def _ready(self, kind: str, data: dict) -> None:
        target = self._job_file
        if not target or not target.is_file():
            return
        current = target == self._file
        draft = self._draft if current else json.loads(target.read_text(encoding="utf-8"))
        if kind == "topic":
            draft["topic"] = data["topic"]
            self._status = "题目已生成。"
        elif kind == "materials":
            draft["materials"] = data["items"]
            if current:
                self._materials = data["items"]
            self._status = f"已生成 {len(data['items'])} 项写作素材。"
        elif kind == "custom_materials":
            existing = {item.get("expression", "").casefold() for item in draft.get("materials", [])}
            new_items = [item for item in data["items"] if item["expression"].casefold() not in existing]
            draft["materials"] = draft.get("materials", []) + new_items
            if current:
                self._materials = draft["materials"]
            self._status = f"已生成 {len(new_items)} 张词汇卡。"
        else:
            draft["review"] = data
            self._status = "批改完成；原稿已保留。"
        atomic_json(target, draft)
        self.refresh()
        self.changed.emit()
        if current and kind == "review":
            self.reviewReady.emit()
        if current and kind == "topic":
            self.topicReady.emit()

    def _failed(self, detail: str) -> None:
        self._status = f"AI 处理失败：{detail}"
        self.changed.emit()

    @Slot(str, str)
    def addNote(self, text: str, source_quote: str) -> None:
        if not text.strip():
            return
        note = {"schema_version": 1, "language": self._draft.get("language", "ja"),
                "text": text.strip(), "sourceQuote": source_quote.strip(),
                "essayTitle": self._draft.get("title", ""), "updated": now()}
        atomic_json(NOTES / f"{uuid4().hex}.json", note)
        self._status = "笔记已保存。"
        self.refresh()
        self.changed.emit()
