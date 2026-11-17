"""Dictionary based Japanese display tokens and conservative timing alignment."""

from __future__ import annotations

import re
import math

_TAGGER = None
_HAN = re.compile(r"[\u3400-\u9fff々〆ヶ]")
_CATEGORY = {
    "名詞": "noun", "代名詞": "noun", "動詞": "verb", "形容詞": "adjective",
    "形状詞": "adjective", "副詞": "adverb", "助詞": "particle", "助動詞": "auxiliary",
}


def cached_display_tokens(text: str, words: list[dict], tokens: object, language='ja') -> list[dict] | None:
    """Reuse saved annotations only when their text and alignment still match."""
    if not isinstance(tokens, list) or not tokens:
        return None
    if language == 'en':
        return tokens if tokens == display_tokens(text, words, language) else None
    if any(not isinstance(t, dict) or not isinstance(t.get('text'), str)
           or not isinstance(t.get('reading'), str)
           or t.get('category') not in {*_CATEGORY.values(), 'other'} for t in tokens):
        return None
    compact = lambda value: ''.join(value.split())
    if compact(''.join(t['text'] for t in tokens)) != compact(text):
        return None
    spans, cursor = [], 0
    for word in words:
        length = len(compact(word['text']))
        if length:
            spans.append((cursor, cursor + length, word['start'], word['end']))
            cursor += length
    aligned = cursor == len(compact(text))
    cursor = 0
    for token in tokens:
        end_offset = cursor + len(compact(token['text']))
        if aligned:
            expected = (_time_at(cursor, spans), _time_at(end_offset, spans))
            actual = (token.get('start'), token.get('end'))
            if any(not isinstance(a, (int, float)) or not math.isfinite(a)
                   or b is None or abs(a - b) > .0011 for a, b in zip(actual, expected)):
                return None
        elif 'start' in token or 'end' in token:
            return None
        cursor = end_offset
    return tokens


def _hiragana(katakana: str) -> str:
    return "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in katakana)


def _time_at(offset: int, spans: list[tuple[int, int, float, float]]) -> float | None:
    boundary: float | None = None
    for begin, finish, start, end in spans:
        if begin <= offset < finish:
            return start + (end - start) * (offset - begin) / max(1, finish - begin)
        if offset == finish:
            boundary = end
    return boundary


def display_tokens(text: str, audio_words: list[dict], language: str = "ja") -> list[dict]:
    global _TAGGER
    if language == "en":
        if audio_words:
            return [{"text": str(word["text"]).strip(), "reading": "", "category": "other",
                     "start": round(float(word["start"]), 3), "end": round(float(word["end"]), 3)}
                    for word in audio_words if str(word.get("text", "")).strip()]
        return [{"text": word, "reading": "", "category": "other"}
                for word in text.split()]
    compact = "".join(text.split())
    spans: list[tuple[int, int, float, float]] = []
    cursor = 0
    for word in audio_words:
        length = len("".join(str(word.get("text", "")).split()))
        if length:
            spans.append((cursor, cursor + length, float(word["start"]), float(word["end"])))
            cursor += length
    aligned = cursor == len(compact)

    tokens: list[dict] = []
    cursor = 0
    if _TAGGER is None:
        from fugashi import Tagger
        _TAGGER = Tagger()
    parsed = list(_TAGGER(text))
    for index, word in enumerate(parsed):
        surface = word.surface
        if not surface:
            continue
        # Fugashi keeps spaces outside the nodes. The compact string also
        # matches Whisper's word sequence when reliable timing is available.
        start_offset = cursor
        cursor += len("".join(surface.split()))
        kana = getattr(word.feature, "kana", "") or ""
        reading = _hiragana(kana) if _HAN.search(surface) and kana not in {"*", ""} else ""
        # The dictionary's default for 方 is ほう. In 学生の方は it refers to
        # people and is read かた; keep comparative uses of 方 untouched.
        if (surface == "方" and index >= 2 and index + 1 < len(parsed)
                and parsed[index - 2].surface == "学生"
                and parsed[index - 1].surface == "の"
                and parsed[index + 1].surface == "は"):
            reading = "かた"
        if surface == "私":
            reading = "わたし"
        elif surface == "日本" and index + 1 < len(parsed) and parsed[index + 1].surface == "語":
            reading = "にほん"
        token = {
            "text": surface,
            "reading": reading,
            "category": _CATEGORY.get(word.feature.pos1, "other"),
        }
        if aligned:
            start = _time_at(start_offset, spans)
            end = _time_at(cursor, spans)
            if start is not None and end is not None:
                token["start"] = round(start, 3)
                token["end"] = round(end, 3)
        tokens.append(token)
    return tokens
