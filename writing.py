"""Writing drafts, AI feedback snapshots, and independent study notes."""

from __future__ import annotations

import html
import os
import math
import json
import re
import sys
from time import perf_counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QThread, QTimer, Signal, Slot

from ai_client import ask_json
from review_guidance import review_english
from writing_tasks import load_tasks

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ESSAYS = ROOT / "data" / "essays"
NOTES = ROOT / "data" / "notes"
FAVORITES = ROOT / "data" / "writing-favorites.json"
MATERIAL_LIBRARY = ROOT / "data" / "writing-materials.json"
WRITING_LAYOUT = ROOT / "data" / "writing-layout.json"
TOKEN_RE = re.compile("\\w+(?:['’]\\w+)*|[^\\w\\s]", re.UNICODE)


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
        if any(phrase in reason for phrase in ('无需修改', '无需更改', '正确，无需', '没有错误')):
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
        for match in re.finditer('[^.!?。！？]+[.!?。！？]*', content):
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
        for match in re.finditer('[^.!?。！？]+[.!?。！？]*', content):
            start, end = offset + match.start(), offset + match.end()
            local = [mark for mark in marks if start <= mark["start"] < end and mark["end"] <= end]
            parts, cursor = [], start
            for mark in sorted(local, key=lambda value: (value["start"], value["end"])):
                if mark["start"] < cursor:
                    continue
                parts.append(html.escape(text[cursor:mark["start"]]))
                color = "#AB3549" if mark["kind"] == "error" else "#A26A28"
                background = "#FFE9ED" if mark["kind"] == "error" else "#FFF0DB"
                shown = text[mark["start"]:mark["end"]] or '＋'
                parts.append(f'<span style="color:{color};background-color:{background};text-decoration:underline">'
                             + html.escape(shown) + "</span>")
                cursor = mark["end"]
            parts.append(html.escape(text[cursor:end]))
            blocks.append({"html": "".join(parts), "gap": False,
                           "notes": [{"quote": mark["quote"], "correction": mark["correction"], "reason": mark["reason"],
                                      "kind": mark["kind"]} for mark in local]})
        offset += len(line)
    return blocks or [{"html": "", "notes": [], "gap": False}]


def review_links(review: dict) -> tuple[list[dict], list[dict]]:
    """Keep the essay in paragraphs and link only unambiguous source spans."""
    source = str(review.get("text", ""))
    issues = []
    candidates = review.get("issues", review.get("marks", [])) if review.get("language") == "en" else review.get("advice", [])
    for item in candidates if isinstance(candidates, list) else []:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", ""))
        correction = str(item.get("correction", item.get("suggestion", "")))
        reason = str(item.get("reason", ""))
        if not quote or not reason:
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or source[start:end] != quote:
            start = source.find(quote) if source.count(quote) == 1 else -1
            end = start + len(quote) if start >= 0 else -1
        issues.append({"quote": quote, "correction": correction, "reason": reason,
                       "category": str(item.get("category", '具体问题')),
                       "kind": str(item.get("kind", "error")),
                       "start": start, "end": end, "linked": start >= 0})
    paragraphs = []
    offset = 0
    for line in source.splitlines(keepends=True) or [""]:
        content = line.rstrip("\r\n")
        spans = [(index, item) for index, item in enumerate(issues)
                 if item["linked"] and offset <= item["start"] < item["end"] <= offset + len(content)]
        cursor = offset
        parts = []
        linked_issues = []
        for index, item in sorted(spans, key=lambda entry: (entry[1]["start"], entry[1]["end"])):
            if item["start"] < cursor:
                item["linked"] = False
                continue
            linked_issues.append(index)
            item["paragraphIndex"] = len(paragraphs)
            parts.append(html.escape(source[cursor:item["start"]]))
            parts.append(f'<a href="issue:{index}" style="color:#365E4C;text-decoration:underline;">'
                         + html.escape(source[item["start"]:item["end"]])
                         + f'<sup style="font-size:10px"> {index + 1}</sup></a>')
            cursor = item["end"]
        parts.append(html.escape(source[cursor:offset + len(content)]))
        paragraphs.append({"html": "".join(parts) or "&nbsp;", "issueIndices": linked_issues})
        offset += len(line)
    return issues, paragraphs


def build_material_prompt(draft: dict, level: str) -> str:
    language = draft.get("language", "ja")
    topic = draft.get("topic", "自由写作")
    mode = draft.get("writing_mode", "practice")
    if language == "en" and mode in {"toefl_email", "toefl_discussion"}:
        task = ("Write an Email：按收件人和目的选择礼貌程度，清楚完成请求、说明或建议。"
                if mode == "toefl_email" else
                "Write for an Academic Discussion：回应讨论，明确立场，并用相关理由或例子展开。")
        return (f"为托福 iBT 写作练习准备 5 条可直接用于当前题目的英语素材。题目：{topic}。"
                f"任务：{task}参考 ETS 写作评分关注的切题、表达清楚、准确自然的词语选择、"
                "适当的句式变化和少量语言错误；不要声称某个词或句式能保证加分，也不要冒充官方词表。"
                "请选 3 条与题目直接相关、常用易记且有明确使用场景的词汇或自然搭配，"
                "以及 2 条能帮助展开理由、举例、限定或礼貌表达的语法/句式。"
                "优先推荐学习者能准确使用的表达，避免冷僻词、堆砌复杂从句、万能开头和模板结尾。"
                "每条提供 expression、kind(grammar/vocabulary)、meaning(不超过 20 字的中文释义)、"
                "usage(1 到 2 行能直接套用的搭配或句型，每行采用‘表达 + 搭配对象/场景’形式，"
                "例如 arrive at + 具体地点；不要写不及物动词、状语等语法术语或长篇解释)、"
                "example(一句贴合题目的自然原创例句，不要返回数组)。只返回 JSON：{\"items\":[...]}。")
    return (f"为{('日语' if language == 'ja' else '英语')}写作练习准备少量真正用得上的表达。"
            f"题目：{topic}。难度：{level}。只给五项：三个与题目直接相关的准确词汇或搭配、"
            "两个可以迁移的自然语法或句式。不要万能开头、万能结尾、套话和生僻词堆砌。"
            "每项给 expression、kind(grammar/vocabulary)、meaning(简短准确的中文释义)、"
            "usage(1 到 2 行可直接使用的搭配或句型，不写长篇语法解释)、"
            "example(一句自然原创例句，不要返回数组)。只返回 JSON：{\"items\":[...]}。")


def build_material_detail_prompt(material: dict) -> str:
    language = "日语" if material.get("language") == "ja" else "英语"
    return (f"为写作时需要立即查用法的学习者整理{language}表达：{material.get('expression', '')}。"
            f"学习原句：{material.get('context', '')}。"
            "只返回 JSON 对象，包含 meaning、usage、example 三个字符串字段。"
            "meaning 是简短准确的中文释义，不超过 30 字。"
            "usage 是 2 到 4 行最常用的直接搭配或句型，每行只写‘表达 + 搭配对象/场景’及必要的极短中文提示；"
            "例如 arrive in + 城市/国家、arrive at + 具体地点、arrive at + 具体时刻、arrive late/tomorrow。"
            "避免‘不及物动词’‘接状语’等术语、编号、长篇说明和罕见用法。"
            "example 是一句自然、原创、能直接借鉴的例句，必须是字符串，不要数组。"
            "尊重表达实际用法，不要硬套以上 arrive 示例；不确定的用法不要编造。")


def material_field_text(value: object, limit: int, max_lines: int = 1) -> str:
    """Keep model arrays from leaking their Python repr into material fields."""
    if isinstance(value, list):
        lines = [str(item).strip() for item in value[:max_lines] if isinstance(item, str) and item.strip()]
        return "\n".join(lines)[:limit]
    if isinstance(value, str):
        return value.strip()[:limit]
    return ""


def material_response_guidance() -> str:
    return ("写作素材卡片用于快速查找。单个词的 usage 用换行分隔 2 到 4 条常用搭配，"
            "每条为表达 + 简短中文使用场景，例如 arrive at + 具体地点、arrive in + 城市或国家、"
            "arrive from + 出发地。已有短语或语法结构无需重复解释本身，另给 related 字段，"
            "用换行分隔 2 到 3 条自然的相近短语或句式，注明简短的使用差别。"
            "不要长篇释义、语法术语和例句；不能确认的相近表达留空。只返回 JSON。")


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
                task = {"toefl_email": 'Write an Email。给出具体情境、收件人、写信目的和两三项必须完成的任务。题面用英文。',
                        "toefl_discussion": 'Write for an Academic Discussion。给出教授提问和两位学生不同的观点，让学习者回应并支持自己的看法。题面用英文。'}.get(
                            mode, '自由写作。给出能激发个人观点的简短主题，不给范文或模板开头。')
                prompt = (f"请为{('日语' if language == 'ja' else '英语')}学习者生成一道模拟练习题：{task}只输出 JSON 对象，字段 topic。题目必须完整、具体，不需要专业背景。不要声称为 ETS 官方题或历年真题，不给官方分数。")
                result = ask_json(prompt, "writing", 700)
                topic = str(result.get("topic", "")).strip()[:1600]
                if not topic:
                    raise ValueError('模型没有返回题目')
                self.resultReady.emit("topic", {"topic": topic})
                return
            if self.mode == "material_detail":
                material = self.draft["material"]
                prompt = build_material_detail_prompt(material) + material_response_guidance()
                result = ask_json(prompt, "writing", 900)
                details = {
                    "meaning": material_field_text(result.get("meaning"), 200),
                    "usage": material_field_text(result.get("usage"), 600, 4),
                    "example": material_field_text(result.get("example"), 400, 2),
                    "related": material_field_text(result.get("related"), 500, 4),
                }
                if not details["usage"] and not details["related"]:
                    raise ValueError('模型没有返回可用的素材解释')
                self.resultReady.emit("material_detail", {"id": material["id"], **details})
                return
            if self.mode == "custom_vocabulary":
                terms = [part.strip() for part in re.split('[,，;；\\n]+', self.level) if part.strip()][:20]
                prompt = (f"为{('日语' if language == 'ja' else '英语')}学习者制作词汇卡。严格只处理给定词，不要添加新词。每项返回 expression、meaning(准确中文释义)、example(自然的原语言例句，展示用法)。只返回 JSON 对象 items 数组。词汇：" + json.dumps(terms, ensure_ascii=False))
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
                    raise ValueError('模型没有返回可用的词汇卡')
                self.resultReady.emit("custom_materials", {"items": items})
                return
            if self.mode == "materials":
                prompt = build_material_prompt(self.draft, self.level) + material_response_guidance()
                result = ask_json(prompt, "writing", 2200)
                items = []
                for item in result.get("items", [])[:20]:
                    if isinstance(item, dict) and item.get("expression"):
                        items.append({
                            "expression": material_field_text(item.get("expression"), 160),
                            "kind": material_field_text(item.get("kind"), 20),
                            "meaning": material_field_text(item.get("meaning"), 200),
                            "usage": material_field_text(item.get("usage"), 400, 3),
                            "example": material_field_text(item.get("example"), 400, 2),
                            "related": material_field_text(item.get("related"), 500, 4),
                        })
                if not items:
                    raise ValueError('模型未给出可用的写作素材')
                self.resultReady.emit("materials", {"items": items})
                return
            text = str(self.draft.get("text", ""))
            if not text.strip():
                raise ValueError('请先写正文')
            targets = self.draft.get("targets", [])
            if language == "en":
                review_started = perf_counter()
                review = review_english(self.draft)
                review["created"] = now()
                review["elapsed_seconds"] = round(perf_counter() - review_started, 1)
                self.progress.emit(1, 1)
            else:
                prompt = (f"你是日语写作指导老师。给中文母语者的作文指出具体语法、用词、自然度与结构问题，特别检查本次目标表达是否自然。不要称为 JLPT 作文考试或官方评分。只返回 JSON 对象，字段 overall、specific_advice(数组，每项含 quote、suggestion、reason)、target_feedback，均用中文说明。\n题目：{self.draft.get('topic', '')}\n本次目标：{targets}\n作文：\n{text}")
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
    materialsChanged = Signal()
    materialChanged = Signal()
    reviewReady = Signal()
    topicReady = Signal()

    def __init__(self, catalogue_path: Path | None = None) -> None:
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
        try:
            saved_library = json.loads(MATERIAL_LIBRARY.read_text(encoding="utf-8"))
            self._library = saved_library.get("items", []) if isinstance(saved_library, dict) else []
        except (OSError, ValueError):
            self._library = []
        # Older library records had no essay owner. Keep them accessible in the
        # explicit collection view instead of showing them in every essay.
        for item in self._library:
            if not item.get("essay_id"):
                item["favorite"] = True
        for favorite in self._favorites:
            if not any(item.get("language") == favorite.get("language")
                       and item.get("expression", "").casefold() == favorite.get("expression", "").casefold()
                       for item in self._library):
                self._library.append({"id": uuid4().hex, "language": favorite.get("language", "ja"),
                                      "kind": favorite.get("kind", "vocabulary"),
                                      "expression": favorite.get("expression", ""),
                                      "meaning": favorite.get("meaning", ""), "usage": "",
                                      "example": favorite.get("example", ""), "context": "",
                                      "note": "", "favorite": True, "essay_id": "",
                                      "updated": now()})
        self._job: WritingJob | None = None
        self._material_job: WritingJob | None = None
        self._job_file: Path | None = None
        self._status = ""
        self._material_status = ""
        try:
            layout = json.loads(WRITING_LAYOUT.read_text(encoding="utf-8"))
            self._side_width = max(270, min(650, int(layout.get("side_width", 314))))
        except (OSError, ValueError, TypeError, AttributeError):
            self._side_width = 314
        assets = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else ROOT
        demo = catalogue_path is None and os.environ.get("JUJIAN_WRITING_DEMO") == "1"
        catalogue = Path(catalogue_path) if catalogue_path is not None else assets / "assets" / "writing-demo.json" if demo else ROOT / "data" / "toefl-writing.json"
        self._tasks = load_tasks(catalogue, allow_demo=demo)
        self._task_live_text = None
        self._clock_started = None
        self._clock_base = 0.0
        self._clock = QTimer(self)
        self._clock.setInterval(250)
        self._clock.timeout.connect(self._tick_task)
        self.refresh()

    @Property("QVariantList", notify=draftsChanged)
    def drafts(self) -> list[dict]: return self._drafts

    @Property("QVariantList", notify=notesChanged)
    def notes(self) -> list[dict]: return self._notes

    @Property("QVariantMap", notify=changed)
    def current(self) -> dict: return self._draft

    @Property(str, notify=changed)
    def currentPath(self) -> str: return str(self._file) if self._file else ""

    @Property(str, notify=changed)
    def currentEssayId(self) -> str: return self._file.stem if self._file else ""

    @Property("QVariantList", notify=changed)
    def materials(self) -> list[dict]: return self._materials

    @Property("QVariantList", notify=changed)
    def favorites(self) -> list[dict]: return self._favorites

    @Property("QVariantList", notify=materialsChanged)
    def library(self) -> list[dict]: return self._library

    @Property("QVariantList", notify=changed)
    def reviewIssues(self) -> list[dict]:
        return review_links(self._draft.get("review", {}))[0]

    @Property("QVariantList", notify=changed)
    def reviewParagraphs(self) -> list[dict]:
        return review_links(self._draft.get("review", {}))[1]

    @Property(str, notify=changed)
    def status(self) -> str: return self._status

    @Property(bool, notify=changed)
    def busy(self) -> bool: return bool(self._job and self._job.isRunning())

    @Property(bool, notify=materialChanged)
    def materialBusy(self) -> bool: return bool(self._material_job and self._material_job.isRunning())

    @Property(str, notify=materialChanged)
    def materialStatus(self) -> str: return self._material_status

    @staticmethod
    def _task_attempt_state(draft: dict) -> str:
        submission = draft.get("submission", {})
        if isinstance(submission, dict) and str(submission.get("text", "")).strip():
            return "completed"
        if not str(draft.get("text", "")).strip():
            return "not_started"
        return "completed" if draft.get("task_state") in {"finished", "editing"} else "in_progress"

    @Property("QVariantList", notify=changed)
    def writingTasks(self) -> list[dict]:
        attempts = {}
        for path in ESSAYS.glob("*.json"):
            try:
                draft = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(draft, dict) and draft.get("task_id"):
                    attempts.setdefault(draft["task_id"], []).append(draft)
            except (OSError, ValueError):
                continue
        rows = []
        for task in self._tasks:
            drafts = attempts.get(task["id"], [])
            completed = [d for d in drafts if self._task_attempt_state(d) == "completed"]
            pending = [d for d in drafts if self._task_attempt_state(d) == "in_progress"]
            state = "in_progress" if pending else "completed" if completed else "not_started"
            completed_at = max((str(d.get("submission", {}).get("at", d.get("updated", ""))) for d in completed), default="")
            rows.append({**task, "state": state,
                         "progress": {"not_started": "未开始", "in_progress": "进行中", "completed": "已完成"}[state],
                         "completed": bool(completed), "completed_at": completed_at,
                         "has_review": any(bool(d.get("review")) for d in drafts),
                         "attempts": len(completed) + len(pending),
                         "latest_activity": max((str(d.get("updated", "")) for d in drafts), default="")})
        return rows

    @Property(int, notify=changed)
    def taskRemaining(self) -> int:
        return max(0, math.ceil(self._draft.get("task_limit", 0) - self._draft.get("task_elapsed", 0)))

    @Slot(str, bool)
    def openWritingTask(self, task_id: str, fresh: bool) -> None:
        task = next((t for t in self._tasks if t["id"] == task_id), None)
        if not task:
            return
        if not fresh:
            candidates = []
            for path in ESSAYS.glob("*.json"):
                try:
                    draft = json.loads(path.read_text(encoding="utf-8"))
                    if draft.get("task_id") == task_id:
                        candidates.append(({"not_started": 0, "completed": 1, "in_progress": 2}[self._task_attempt_state(draft)], draft.get("updated", ""), path))
                except (OSError, ValueError):
                    pass
            if candidates:
                self.openDraft(str(max(candidates)[2]))
                return
        self.newDraft("en")
        self._draft.update({"title": task["set_title"] + " · " + task["title"],
                            "writing_mode": task["kind"], "topic": task["prompt"],
                            "topic_source": task["review_status"], "task_id": task["id"],
                            "set_id": task["set_id"], "task_version": task["version"],
                            "task_prompt": task["prompt"], "task_source": task["source"],
                            "task_limit": task["limit_seconds"], "task_elapsed": 0.0,
                            "task_state": "ready", "attempt_id": self._file.stem})
        atomic_json(self._file, self._draft)
        self.refresh()
        self.changed.emit()
        self.topicReady.emit()

    def _persist_task(self) -> None:
        if self._file:
            self._draft["updated"] = now()
            atomic_json(self._file, self._draft)
        self.changed.emit()

    @Slot(str)
    def updateTaskText(self, text: str) -> None:
        # Keep the deadline snapshot current even during the autosave debounce.
        if self._draft.get("task_id") and self._draft.get("task_state") != "finished":
            self._task_live_text = (self.currentPath, text)

    @Slot()
    def startTask(self) -> None:
        if self._draft.get("task_state") not in {"ready", "paused"}:
            return
        self._clock_base = float(self._draft.get("task_elapsed", 0))
        self._clock_started = perf_counter()
        self._draft["task_state"] = "running"
        self._clock.start()
        self._persist_task()

    def _tick_task(self) -> None:
        if self._clock_started is None:
            return
        elapsed = min(float(self._draft["task_limit"]), self._clock_base + perf_counter() - self._clock_started)
        previous = self._draft.get("task_elapsed", 0)
        self._draft["task_elapsed"] = elapsed
        if elapsed >= self._draft["task_limit"]:
            self._finish_task("timeout")
        elif int(previous) != int(elapsed):
            self._persist_task()

    @Slot()
    def pauseTask(self) -> None:
        if self._clock_started is None:
            return
        self._tick_task()
        if self._draft.get("task_state") == "running":
            self._draft["task_state"] = "paused"
            self._clock.stop()
            self._clock_started = None
            self._persist_task()

    def _finish_task(self, reason: str) -> None:
        self._clock.stop()
        self._clock_started = None
        if self._task_live_text and self._task_live_text[0] == self.currentPath:
            self._draft["text"] = self._task_live_text[1]
        self._draft["task_state"] = "finished"
        if "submission" not in self._draft:
            self._draft["submission"] = {"text": self._draft.get("text", ""),
                                         "elapsed": self._draft.get("task_elapsed", 0),
                                         "reason": reason, "at": now()}
        self._status = "时间到，原稿已保存。" if reason == "timeout" else "作答结束，原稿已保存。"
        self._persist_task()
        self.refresh()

    @Slot()
    def finishTask(self) -> None:
        if not self._draft.get("task_id") or self._draft.get("task_state") in {"finished", "editing"}:
            return
        self.pauseTask()
        if self._draft.get("task_state") != "finished":
            self._finish_task("manual")

    @Slot()
    def editTask(self) -> None:
        if self._draft.get("task_state") == "finished":
            self._draft["task_state"] = "editing"
            self._persist_task()

    @Slot()
    def untimedTask(self) -> None:
        if self._draft.get("task_state") not in {"ready", "paused", "untimed"}:
            return
        self._draft["task_state"] = "ready" if self._draft["task_state"] == "untimed" else "untimed"
        self._persist_task()

    @Slot()
    def clearMaterialStatus(self) -> None:
        if not self.materialBusy and self._material_status:
            self._material_status = ""
            self.materialChanged.emit()

    @Property(int, notify=changed)
    def sideWidth(self) -> int: return self._side_width

    @Slot(QObject)
    def setDraftLineSpacing(self, editor: QObject) -> None:
        """Apply editor-only line spacing without changing the saved plain text."""
        if editor is None or self._draft.get("language") != "en":
            return
        from PySide6.QtGui import QTextBlockFormat, QTextCursor
        from PySide6.QtQuick import QQuickTextDocument

        quick_document = editor.property("textDocument")
        if not isinstance(quick_document, QQuickTextDocument):
            return
        document = quick_document.textDocument()
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.Document)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(140, QTextBlockFormat.ProportionalHeight.value)
        undo_enabled = document.isUndoRedoEnabled()
        document.setUndoRedoEnabled(False)
        cursor.mergeBlockFormat(block_format)
        document.setUndoRedoEnabled(undo_enabled)

    @Slot(int)
    def setSideWidth(self, width: int) -> None:
        width = max(270, min(650, width))
        if width == self._side_width:
            return
        self._side_width = width
        atomic_json(WRITING_LAYOUT, {"side_width": width})
        self.changed.emit()

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
                drafts.append({"path": str(path), "title": data.get("title") or '未命名作文',
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
                essay_id = data.get("essay_id", "")
                linked = next((d for d in drafts if Path(d["path"]).stem == essay_id), None) if essay_id else None
                if not linked and not essay_id and data.get("essayTitle"):
                    by_title = [d for d in drafts if d["title"] == data["essayTitle"]]
                    linked = by_title[0] if len(by_title) == 1 else None
                notes.append({**data, "path": str(path), "essayPath": linked["path"] if linked else "",
                              "essayTitle": linked["title"] if linked else data.get("essayTitle", "")})
            except (OSError, ValueError):
                continue
        self._notes = sorted(notes, key=lambda item: item.get("updated", ""), reverse=True)
        self.notesChanged.emit()

    @Slot(str)
    def newDraft(self, language: str) -> None:
        if language not in {"ja", "en"}:
            language = "ja"
        self.pauseTask()
        self._file = ESSAYS / f"{uuid4().hex}.json"
        self._draft = {"schema_version": 1, "title": '未命名作文', "language": language,
                       "topic": "", "text": "", "targets": [], "writing_mode": "practice",
                       "practice_style": "guided", "topic_source": "custom",
                       "side_open": False,
                       "created": now(), "updated": now()}
        self._materials = []
        self._status = ""
        atomic_json(self._file, self._draft)
        self.refresh()
        self.changed.emit()

    @Slot(str)
    def openDraft(self, path: str) -> None:
        self.pauseTask()
        file = Path(path)
        if file.parent != ESSAYS or not file.is_file():
            self._status = '作文不存在。'
            self.changed.emit()
            return
        try:
            self._draft = json.loads(file.read_text(encoding="utf-8"))
            self._file = file
            if self._draft.get("task_state") == "running":
                self._draft["task_state"] = "paused"
                atomic_json(file, self._draft)
            self._materials = self._draft.get("materials", [])
            self._status = '已打开作文。'
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self._status = f'打开作文失败：{exc}'
            self.changed.emit()

    @Slot(str, str, str)
    def saveDraft(self, title: str, topic: str, text: str) -> None:
        if not self._file:
            return
        if self._draft.get("task_id"):
            topic = self._draft["task_prompt"]
        fields = {"title": title.strip() or '未命名作文', "topic": topic.strip(), "text": text}
        if all(self._draft.get(key) == value for key, value in fields.items()):
            return
        if fields["topic"] != self._draft.get("topic", ""):
            self._draft["topic_source"] = "custom"
        self._draft.update({**fields, "updated": now()})
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

    def _save_library(self) -> None:
        atomic_json(MATERIAL_LIBRARY, {"schema_version": 2, "items": self._library})
        self.materialsChanged.emit()

    @Slot(str, str, str, str, str, result=str)
    def saveMaterial(self, language: str, kind: str, expression: str, context: str, note: str) -> str:
        expression = expression.strip()[:160]
        if not expression or language not in {"ja", "en"} or kind not in {"grammar", "vocabulary"}:
            self._status = '请填写词语或语法内容。'
            self.changed.emit()
            return ""
        essay_id = self.currentEssayId
        existing = next((item for item in self._library if item.get("essay_id", "") == essay_id
                         and item.get("language") == language
                         and item.get("kind") == kind
                         and item.get("expression", "").casefold() == expression.casefold()), None)
        if existing:
            if context.strip() and not existing.get("context"):
                existing["context"] = context.strip()[:1000]
            if note.strip() and note.strip() not in existing.get("note", ""):
                existing["note"] = (existing.get("note", "") + "\n" + note.strip()).strip()[:2000]
            existing["updated"] = now()
            self._save_library()
            self._status = '已找到这条素材，并补上新的原句或笔记。'
            self.changed.emit()
            return str(existing["id"])
        item = {"id": uuid4().hex, "language": language, "kind": kind,
                "expression": expression, "context": context.strip()[:1000],
                "note": note.strip()[:2000], "meaning": "", "usage": "", "example": "",
                "essay_id": essay_id, "favorite": not bool(essay_id),
                "updated": now()}
        self._library.insert(0, item)
        self._save_library()
        self._status = '已收录到个人素材库。'
        self.changed.emit()
        return item["id"]

    @Slot(str)
    def toggleMaterialFavorite(self, item_id: str) -> None:
        item = next((value for value in self._library if value.get("id") == item_id), None)
        if not item or not item.get("essay_id"):
            return
        item["favorite"] = not bool(item.get("favorite"))
        item["updated"] = now()
        self._save_library()

    @Slot(str, result=str)
    def copyMaterialToCurrentEssay(self, item_id: str) -> str:
        item = next((value for value in self._library if value.get("id") == item_id), None)
        if not item or not self.currentEssayId:
            return ""
        copied_id = self.saveMaterial(item.get("language", "en"), item.get("kind", "vocabulary"),
                                      item.get("expression", ""), item.get("context", ""), item.get("note", ""))
        copied = next((value for value in self._library if value.get("id") == copied_id), None)
        if copied and copied_id != item_id:
            for key in ("meaning", "usage", "example", "related"):
                if not copied.get(key):
                    copied[key] = item.get(key, "")
            self._save_library()
        return copied_id

    @Slot(str, str, str, str, str)
    def updateMaterial(self, item_id: str, meaning: str, usage: str, example: str, note: str) -> None:
        item = next((value for value in self._library if value.get("id") == item_id), None)
        if not item:
            return
        item.update({"meaning": meaning.strip()[:2000], "usage": usage.strip()[:2000],
                     "example": example.strip()[:1000], "note": note.strip()[:2000],
                     "updated": now()})
        self._save_library()
        self._status = '素材已保存。'
        self.changed.emit()

    @Slot(str, str)
    def updateMaterialRelated(self, item_id: str, related: str) -> None:
        item = next((value for value in self._library if value.get("id") == item_id), None)
        if item:
            item["related"] = related.strip()[:1000]
            item["updated"] = now()
            self._save_library()

    @Slot(str)
    def deleteMaterial(self, item_id: str) -> None:
        remaining = [item for item in self._library if item.get("id") != item_id]
        if len(remaining) == len(self._library):
            return
        self._library = remaining
        self._save_library()
        self._status = '素材已删除。'
        self.changed.emit()

    @Slot(str)
    def enrichMaterial(self, item_id: str) -> None:
        if self.materialBusy:
            return
        item = next((value for value in self._library if value.get("id") == item_id), None)
        if not item:
            return
        self._material_status = '正在补充含义和用法…'
        self._material_job = WritingJob("material_detail", {"material": dict(item)})
        self._material_job.resultReady.connect(self._material_ready)
        self._material_job.failed.connect(self._material_failed)
        self._material_job.finished.connect(self.materialChanged.emit)
        self._material_job.start()
        self.materialChanged.emit()

    def _material_ready(self, kind: str, data: dict) -> None:
        if kind != "material_detail":
            return
        item = next((value for value in self._library if value.get("id") == data["id"]), None)
        if item:
            for key in ("meaning", "usage", "example", "related"):
                existing = str(item.get(key, "")).strip()
                suggested = data.get(key, "")
                if suggested and (key in {"usage", "related"} or not existing):
                    item[key] = suggested
            item["updated"] = now()
            self._save_library()
            self._material_status = 'AI 已补充用法；可自行核对和编辑。'
            self.materialChanged.emit()

    def _material_failed(self, detail: str) -> None:
        self._material_status = f'AI 补充失败：{detail}'
        self.materialChanged.emit()

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
        self._status = '作文已删除。'
        self.refresh()

    @Slot(str, str)
    def addCustomMaterials(self, text: str, kind: str) -> None:
        if not self._file or self.busy:
            return
        terms = list(dict.fromkeys(part.strip() for part in re.split('[,，;；\\n]+', text) if part.strip()))[:20]
        if not terms:
            return
        if kind == "grammar":
            existing = {item.get("expression", "").casefold() for item in self._materials}
            self._materials.extend({"expression": term, "kind": "grammar", "meaning": "", "example": ""}
                                   for term in terms if term.casefold() not in existing)
            self._draft["materials"] = self._materials
            atomic_json(self._file, self._draft)
            self._status = f'已添加 {len(terms)} 项语法卡。'
            self.changed.emit()
            return
        self._status = '正在生成词汇卡…'
        self._job = WritingJob("custom_vocabulary", dict(self._draft), "\n".join(terms))
        self._job_file = self._file
        self._job.resultReady.connect(self._ready)
        self._job.failed.connect(self._failed)
        self._job.finished.connect(self.changed.emit)
        self._job.start()
        self.changed.emit()

    @Slot(str)
    def setMode(self, mode: str) -> None:
        if self._draft.get("task_id"):
            return
        if not self._file or mode not in {"practice", "toefl_email", "toefl_discussion"}:
            return
        if self._draft.get("language") == "ja" and mode != "practice":
            return
        self._draft["writing_mode"] = mode
        atomic_json(self._file, self._draft)
        self.changed.emit()

    @Slot(str)
    def setPracticeStyle(self, style: str) -> None:
        if self._draft.get("task_id"):
            return
        if not self._file or style not in {"guided", "timed"}:
            return
        self._draft["practice_style"] = style
        atomic_json(self._file, self._draft)
        self.changed.emit()

    @Slot(bool)
    def setSideOpen(self, opened: bool) -> None:
        if not self._file or self._draft.get("side_open", False) == opened:
            return
        self._draft["side_open"] = opened
        atomic_json(self._file, self._draft)
        self.changed.emit()

    @Slot(str, str)
    def setOfficialTopic(self, topic: str, source_url: str) -> None:
        if not self._file or self._draft.get("writing_mode") not in {"toefl_email", "toefl_discussion"}:
            return
        topic = topic.strip()[:4000]
        if not topic:
            return
        self._draft["topic"] = topic
        self._draft["topic_source"] = "ets_user_entry"
        self._draft["topic_url"] = source_url.strip()[:500]
        atomic_json(self._file, self._draft)
        self._status = '已收录从 ETS 练习材料录入的题目。'
        self.changed.emit()
        self.topicReady.emit()

    @Slot()
    def generateTopic(self) -> None:
        if self.busy or not self._file or self._draft.get("task_id"):
            return
        self._status = '正在生成写作题目…'
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
        self._status = '正在生成写作素材…'
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
        if self._draft.get("task_id") and self._draft.get("task_state") not in {"finished", "editing", "untimed"}:
            return
        self._status = '正在通读整篇作文并整理建议…'
        self._job = WritingJob("review", dict(self._draft))
        self._job_file = self._file
        self._job.resultReady.connect(self._ready)
        self._job.failed.connect(self._failed)
        self._job.progress.connect(self._progress)
        self._job.finished.connect(self.changed.emit)
        self._job.start()
        self.changed.emit()

    def _progress(self, completed: int, total: int) -> None:
        self._status = '正在整理批改结果…'
        self.changed.emit()

    def _ready(self, kind: str, data: dict) -> None:
        target = self._job_file
        if not target or not target.is_file():
            return
        current = target == self._file
        draft = self._draft if current else json.loads(target.read_text(encoding="utf-8"))
        if kind == "topic":
            draft["topic"] = data["topic"]
            draft["topic_source"] = "ai"
            self._status = '题目已生成。'
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
            self._status = f'已生成 {len(new_items)} 张词汇卡。'
        else:
            draft["review"] = data
            self._status = '批改完成；原稿已保留。'
        atomic_json(target, draft)
        self.refresh()
        self.changed.emit()
        if current and kind == "review":
            self.reviewReady.emit()
        if current and kind == "topic":
            self.topicReady.emit()

    def _failed(self, detail: str) -> None:
        self._status = f'AI 处理失败：{detail}'
        self.changed.emit()

    @Slot(str, str, str, str, str, result=bool)
    def saveWritingNote(self, path: str, text: str, source_quote: str, essay_path: str, language: str) -> bool:
        if not text.strip() and not source_quote.strip():
            return False
        note_file = Path(path) if path else NOTES / f"{uuid4().hex}.json"
        if note_file.parent.resolve() != NOTES.resolve() or note_file.suffix != ".json":
            return False
        note = {}
        if path:
            try:
                note = json.loads(note_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
        essay = next((d for d in self._drafts if d["path"] == essay_path), None)
        if essay_path and not essay:
            self._status = '原作文已不存在，请重新选择关联。'
            self.changed.emit()
            return False
        # An older note may have only a title; editing its content preserves that history.
        legacy_title = note.get("essayTitle", "") if not note.get("essay_id") and not essay else ""
        note.update({"schema_version": 2, "language": essay["language"] if essay else ("ja" if language == "ja" else "en"),
                     "text": text.strip(), "sourceQuote": source_quote.strip(),
                     "essay_id": Path(essay["path"]).stem if essay else "",
                     "essayTitle": essay["title"] if essay else legacy_title, "updated": now()})
        atomic_json(note_file, note)
        self._status = '笔记已保存。'
        self.refresh()
        self.changed.emit()
        return True

    @Slot(str, str)
    def addNote(self, text: str, source_quote: str) -> None:
        self.saveWritingNote("", text, source_quote, self.currentPath, self._draft.get("language", "ja"))
