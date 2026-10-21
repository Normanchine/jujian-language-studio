"""Conservative listening units from immutable English words and their timestamps."""
from __future__ import annotations

import copy
import json
import math
import re
from urllib.request import Request, urlopen
from urllib.error import URLError

MODEL = "qwen3-8b-nothink:latest"
VERSION = 1
STOP = set("a an the to of and but or is are be being my your our their through quite just taken shall instead".split())


def compact(text):
    return re.sub(r"\s+", "", text)


def local_json(prompt, schema, limit=512):
    payload = {"model": MODEL, "prompt": prompt, "format": schema, "stream": False, "think": False,
               "options": {"temperature": 0, "num_ctx": 4096, "num_predict": limit}}
    request = Request("http://127.0.0.1:11434/api/generate", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=35) as response:
        raw = json.load(response)
    if raw.get("done_reason") == "length":
        raise ValueError("本地模型输出被截断")
    return json.loads(raw["response"])


def sentence_end(text):
    return bool(re.search(r"[.!?][\"')\]]?$", text.strip())) and text.strip() not in {"Mr.", "Mrs.", "Dr.", "Ms.", "U.S."}


def candidates_for(words):
    candidates, mandatory = {len(words)}, set()
    for i, word in enumerate(words, 1):
        text = word["text"].strip()
        if sentence_end(text):
            candidates.add(i)
            mandatory.add(i)
        elif re.search(r"[,;:]$", text):
            candidates.add(i)
        elif i < len(words) and text.lower() not in STOP:
            if words[i]["text"].strip().lower() == "instead" or words[i]["start"] - word["end"] >= 0.35:
                candidates.add(i)
    return sorted(candidates), mandatory


def choose_boundaries(words, use_model=False):
    candidates, mandatory = candidates_for(words)
    suggested = set()
    used_model = False
    if use_model and len(words) <= 180:
        pieces, previous = [], 0
        for end in candidates:
            pieces.append(f"end_word={end}: {''.join(w['text'] for w in words[previous:end]).strip()}")
            previous = end
        schema = {"type": "object", "properties": {"end_words": {"type": "array",
                  "items": {"type": "integer", "enum": candidates}}}, "required": ["end_words"], "additionalProperties": False}
        answer = local_json("Select natural English listening unit boundaries. Join adjacent candidate pieces as needed. "
                            "Prefer 10-25 words per unit. Avoid cutting phrases. Keep complete sentences separate. "
                            f"Return increasing end_words including sentence ends {sorted(mandatory)} and final {len(words)}.\n"
                            + "\n".join(pieces), schema)
        ends = answer.get("end_words", [])
        if ends and all(isinstance(i, int) and not isinstance(i, bool) for i in ends) and ends == sorted(set(ends)):
            if set(ends).issubset(candidates) and mandatory.issubset(ends) and ends[-1] == len(words):
                suggested = set(ends)
                used_model = True
    # Add conservative emergency candidates only for long unpunctuated spans.
    nodes = sorted({0, *candidates, *(i for i, word in enumerate(words, 1)
                                      if word["text"].strip().lower() not in STOP)})
    costs, paths = {0: 0.0}, {0: []}
    for end in nodes[1:]:
        for begin in reversed(nodes):
            if begin >= end or begin not in costs:
                continue
            count = end - begin
            if count > 32:
                break
            duration = words[end - 1]["end"] - words[begin]["start"]
            if duration <= 0 or duration > 14 or any(begin < boundary < end for boundary in mandatory):
                continue
            cost = 1.5 + abs(count - 18) * 0.13 + abs(duration - 7) * 0.18
            if end not in candidates:
                cost += 7
            if count < 6 and end not in mandatory:
                cost += 10
            if end in suggested:
                cost -= 1
            value = costs[begin] + cost
            if value < costs.get(end, math.inf):
                costs[end], paths[end] = value, [*paths[begin], end]
    if len(words) not in paths:
        raise ValueError("逐词时间不足以安全拆分")
    return paths[len(words)], used_model


def translate_unit(text):
    schema = {"type": "object", "properties": {"translation": {"type": "string"}},
              "required": ["translation"], "additionalProperties": False}
    result = local_json("把下面英语口语片段完整译成自然的简体中文。保留否定、疑问和不确定语气；不要省略列举，"
                        "不要增添含义或解释。本段可能是长句的一部分。只返回JSON translation。\n本段原文：" + text, schema, 384)
    translation = str(result.get("translation", "")).strip()
    if not translation:
        raise ValueError("本地模型未返回译文")
    return translation


def eligible(segment):
    words = segment.get("words", [])
    return (not segment.get("reviewed") and segment.get("analysis", {}).get("model") != "manual" and bool(words)
            and compact("".join(w.get("text", "") for w in words)) == compact(segment.get("text", "")))


def split_japanese_segments(segments, cancelled=None):
    """Use existing word times, sentence endings and pauses; never invent word times."""
    output = []
    audit = {"changed": False, "protected": 0, "model_groups": 0, "fallback_groups": 0,
             "original_count": len(segments)}
    ending = re.compile(r"(?:ですか|ますか|ませんか|でしょうか|でした|ました|ません|です|ます|ですね|ですよ|だね|だよ|そうか)[。！？!?」』]*$")
    for segment in segments:
        if cancelled and cancelled():
            raise InterruptedError("整理已取消，原字幕保持不变")
        if not eligible(segment):
            output.append(copy.deepcopy(segment)); audit["protected"] += 1
            continue
        words = segment["words"]
        if any(a["end"] > b["start"] or a["end"] < a["start"] for a, b in zip(words, words[1:])):
            output.append(copy.deepcopy(segment)); audit["protected"] += 1
            continue
        ends, begin = [], 0
        for i in range(1, len(words)):
            text = "".join(w["text"] for w in words[begin:i]).strip()
            following = words[i]["text"]
            gap = words[i]["start"] - words[i-1]["end"]
            duration = words[i-1]["end"] - words[begin]["start"]
            remaining = words[-1]["end"] - words[i]["start"]
            punctuation = bool(re.search(r"[。！？!?][」』]*$", text))
            # Do not separate a question/final particle from its predicate.
            terminal = bool(ending.search(text)) and not re.match(r"^[かねよなぞ][。！？!?、\s]*$", following.strip())
            boundary = punctuation or (terminal and (gap >= .2 or following[:1].isspace()))
            long_clause = duration >= 7 and gap >= .45 and bool(re.search(r"[、,]|(?:けど|から|ので|が|て)$", text))
            if duration >= 1.2 and remaining >= 1.2 and len(compact(text)) >= 4 and (boundary or long_clause):
                ends.append(i); begin = i
        if not ends:
            output.append(copy.deepcopy(segment)); continue
        begin = 0
        for end in [*ends, len(words)]:
            selected = copy.deepcopy(words[begin:end])
            unit = {"start": selected[0]["start"], "end": selected[-1]["end"],
                    "text": "".join(w["text"] for w in selected).strip(), "words": selected,
                    "translation": "", "analysis": {}, "reviewed": False,
                    "split_method": "ja-source-word-timestamps-v1"}
            output.append(unit); begin = end
        audit["changed"] = True
    audit["unit_count"] = len(output)
    return output, audit


def split_segments(segments, language="en", use_model=False, translate_new=False, progress=None, cancelled=None):
    """Return new segments and audit. Protected/un-aligned segments remain exact copies."""
    if language == "ja":
        return split_japanese_segments(segments, cancelled)
    if language != "en":
        return copy.deepcopy(segments), {"changed": False, "protected": len(segments), "model_groups": 0, "fallback_groups": 0}
    output, group = [], []
    audit = {"changed": False, "protected": 0, "model_groups": 0, "fallback_groups": 0, "translation_failures": 0, "model_errors": []}
    model_available = True
    failure_streak = 0

    def check_cancel():
        if cancelled and cancelled():
            raise InterruptedError("整理已取消，原字幕保持不变")

    def flush():
        nonlocal group, model_available, failure_streak
        if not group:
            return
        check_cancel()
        words = [copy.deepcopy(word) for segment in group for word in segment["words"]]
        canonical = "".join(segment["text"] for segment in group)
        try:
            try:
                ends, model_used = choose_boundaries(words, use_model and model_available)
            except (OSError, ValueError, KeyError, TypeError, TimeoutError) as exc:
                failure_streak = failure_streak + 1 if isinstance(exc, (URLError, TimeoutError)) else 0
                model_available = failure_streak < 3
                if len(audit["model_errors"]) < 10:
                    audit["model_errors"].append(str(exc)[:180])
                ends, model_used = choose_boundaries(words, False)
                audit["fallback_groups"] += 1
            audit["model_groups"] += int(model_used)
            units, previous = [], 0
            for end in ends:
                check_cancel()
                selected = words[previous:end]
                text = "".join(word["text"] for word in selected).strip()
                existing = next((s for s in group if s["start"] == selected[0]["start"]
                                 and s["end"] == selected[-1]["end"] and compact(s["text"]) == compact(text)), None)
                if existing:
                    unit = copy.deepcopy(existing)
                else:
                    unit = {"start": selected[0]["start"], "end": selected[-1]["end"], "text": text,
                            "words": selected, "translation": "", "analysis": {}, "reviewed": False,
                            "split_method": "source-word-timestamps-v1"}
                    if translate_new and model_available:
                        try:
                            unit["analysis"] = {"source_text": text, "translation": translate_unit(text),
                                                "translation_model": MODEL, "grammar": "", "vocabulary": []}
                            failure_streak = 0
                        except (OSError, ValueError, KeyError, TypeError, TimeoutError) as exc:
                            audit["translation_failures"] += 1
                            failure_streak = failure_streak + 1 if isinstance(exc, (URLError, TimeoutError)) else 0
                            model_available = failure_streak < 3
                            if len(audit["model_errors"]) < 10:
                                audit["model_errors"].append(str(exc)[:180])
                    if progress:
                        progress(len(output) + len(units) + 1, len(segments))
                units.append(unit)
                previous = end
            if compact("".join(unit["text"] for unit in units)) != compact(canonical):
                raise ValueError("分段结果未完整覆盖原文")
            if any(a["end"] > b["start"] for a, b in zip(units, units[1:])):
                raise ValueError("分段时间重叠")
            output.extend(units)
        except (ValueError, KeyError, TypeError):
            output.extend(copy.deepcopy(group))
            audit["protected"] += len(group)
        group = []

    for segment in segments:
        check_cancel()
        if not eligible(segment):
            flush()
            output.append(copy.deepcopy(segment))
            audit["protected"] += 1
            continue
        if group and segment["start"] - group[-1]["end"] > 2.5:
            flush()
        group.append(segment)
        if sentence_end(segment["text"]) or sum(len(s["words"]) for s in group) >= 180:
            flush()
    flush()
    if compact("".join(s["text"] for s in output)) != compact("".join(s["text"] for s in segments)):
        raise ValueError("原文覆盖检查失败")
    if any(a["end"] > b["start"] for a, b in zip(output, output[1:])):
        raise ValueError("时间顺序检查失败")
    audit["changed"] = [(s["text"], s["start"], s["end"]) for s in output] != [(s["text"], s["start"], s["end"]) for s in segments]
    audit["original_count"], audit["unit_count"] = len(segments), len(output)
    return output, audit
