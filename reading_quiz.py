"""Deterministic parsing of reading passages that carry multiple-choice questions.

The importer works on plain text pasted from a document, a TXT file or a
Markdown file.  It never guesses a question it cannot see: text that does not
contain a numbered question with at least two options is rejected so the
article can still be imported through the intensive-reading flow.
"""
from __future__ import annotations

import re

MAX_TEXT = 500_000
LETTERS = "ABCDEF"
JP_LETTERS = "アイウエオ"
CIRCLED = "①②③④⑤⑥"

_SECTION = re.compile(
    r"^(?:(?:passage|text|reading|section|part|reading\s+passage)\s*(\d{1,2})"
    r"|(?:阅读材料|阅读文章|文章|阅读)\s*(\d{1,2})"
    r"|第\s*(\d{1,2})\s*(?:篇|章|部分))"
    r"\s*[：:．.、\-—]?\s*(.*)$",
    re.I,
)
_QUESTIONS_HEADING = re.compile(r"^(?:questions?|questions?\s*[:：].*|题目|问题|试题)$", re.I)
_QUESTION = re.compile(r"^(?:(?:question|q)\s*)?(\d{1,3})\s*[\.．、\)）:：]\s*(.*)$", re.I)
_QUESTION_JP = re.compile(r"^(?:第\s*)?(\d{1,3})\s*問\s*[\.．、:：]?\s*(.*)$")
_QUESTION_JP2 = re.compile(r"^問\s*(\d{1,3})\s*[\.．、:：]?\s*(.*)$")
_OPTION = re.compile(r"^[\(（]?\s*([A-Ha-h]|[アイウエオ])\s*[\)）\.．、:：]\s*(\S.*)$")
_OPTION_SPACE = re.compile(r"^([A-Ha-h]|[アイウエオ])\s+(\S.*)$")
_OPTION_CIRCLED = re.compile(r"^([①②③④⑤⑥])\s*(\S.*)$")
_ANSWER_LINE = re.compile(
    r"^(?:correct\s+answer|answer|answers|key|答案|参考答案|正确答案|正解|答え|こたえ)\s*[:：]?\s*"
    r"([A-Ha-h]|[アイウエオ]|[1-6]|[①②③④⑤⑥])",
    re.I,
)
_KEY_HEADER = re.compile(
    r"^(?:(?:答案|参考答案|正确答案|正解|答え|こたえ)\s*[:：]?\s*"
    r"|(?:answer\s+key|answers?|key|keys)\b\s*[:：]?\s*)(.*)$",
    re.I,
)
_PAIR = re.compile(
    r"(?<![\dA-Za-z])(\d{1,3})\s*[\.．、\)）:：\-—]?\s*"
    r"([A-Ha-h]|[アイウエオ]|[①-⑥])(?![A-Za-z0-9])"
)
_BOLD_OPTION = re.compile(r"(\*\*|__)\s*[\(（]?([A-Ha-h]|[アイウエオ])[\)）\.．、:：]")
_CHECK_MARK = re.compile(r"[✓✔√]\s*$")
_EXPLANATION = re.compile(r'^(?:explanation|解析|解説|解答解説)\s*[:：]?\s*(.*)$', re.I)
_BARE_PAIR = re.compile(
    r"^[\(（]?\s*(\d{1,3})\s*[\.．、\)）:：\-—]?\s*[\(（]?\s*"
    r"([A-Ha-h]|[アイウエオ]|[①-⑥])\s*[\)）]?$"
)
_INSTRUCTION = re.compile(r"^第\s*\d+\s*問|^(?:directions?|instructions?)\s*[:：]", re.I)
_NOISE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")


def _clean(line: str) -> str:
    """Strip layout marks that do not change the text itself."""
    text = line.strip()
    text = re.sub(r"^>+\s*", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^[-*+]\s+(?=\S)", "", text)
    text = re.sub(r'\\([.()])', r'\1', text)
    # Bold/italic markers wrap numbers, stems and options.  Keep the words and
    # drop the markers; bold option lines are still recognised from the raw
    # line before this cleanup runs.
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^[*_]{1,3}(.+?)[*_]{1,3}$", r"\1", text)
    return text.replace("`", "").strip()


def _letter(value: str, options_count: int) -> str:
    value = (value or "").strip()
    if not value:
        return ''
    if value in JP_LETTERS:
        value = LETTERS[JP_LETTERS.index(value)]
    if value in CIRCLED:
        value = LETTERS[CIRCLED.index(value)]
    if value.isdigit():
        index = int(value) - 1
        return LETTERS[index] if 0 <= index < options_count else ""
    value = value.upper()
    return value if value in LETTERS[:options_count] else ""


def _normalize(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("请先粘贴正文，或选择一个 TXT / Markdown 文件。")
    if len(raw) > MAX_TEXT or "\x00" in raw:
        raise ValueError("正文过长或含有二进制字符，请拆分为纯文本。")
    text = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    return text


def _join(lines, language):
    if not lines:
        return ""
    output = lines[0]
    for line in lines[1:]:
        space = language == "en" or (
            bool(re.search(r"[A-Za-z0-9]$", output)) and bool(re.match(r"[A-Za-z0-9]", line))
        )
        output += (" " if space else "") + line
    return output


def _section_marks(lines):
    marks = []
    for index, line in enumerate(lines):
        text = _clean(line)
        match = _SECTION.match(text)
        if not match:
            continue
        title = match.group(4).strip()
        if re.search(r"(?:^|\s)questions?\s*$", title, re.I):
            # "Passage 1 Questions" introduces the questions, not a new passage.
            continue
        number = match.group(1) or match.group(2) or match.group(3)
        marks.append((index, int(number), title))
    return marks


def _question_start(text):
    for pattern in (_QUESTION_JP2, _QUESTION_JP, _QUESTION):
        match = pattern.match(text)
        if match:
            return int(match.group(1)), match.group(2).strip()
    return None


def _option_start(text):
    match = _OPTION.match(text)
    if match:
        return match.group(1), match.group(2).strip()
    match = _OPTION_CIRCLED.match(text)
    if match:
        return match.group(1), match.group(2).strip()
    return None


def _option_space(text):
    match = _OPTION_SPACE.match(text)
    if match:
        return match.group(1), match.group(2).strip()
    return None


def _is_bold_option(raw):
    return bool(_BOLD_OPTION.search(raw) or _CHECK_MARK.search(raw))


def _pairs(text):
    output = []
    for number, letter in _PAIR.findall((text or '').replace('|', ' ')):
        output.append((int(number), _letter(letter, 6)))
    return [(number, letter) for number, letter in output if letter]


def _table_noise(text):
    if re.fullmatch(r'[\s|:\-]+', text):
        return True
    cells = [c.strip().casefold() for c in text.strip('|').split('|')]
    return len(cells) > 1 and all(c in {'question', 'no.', 'no', 'number', 'answer', 'answers', '题号', '答案', '题目'} for c in cells)


def _key_row(text):
    return bool(_pairs(text)) and not re.sub(r'[\s,，;；、/|]+', '', _PAIR.sub('', text.replace('|', ' ')))


def _collect_answer_key(lines):
    """Read an answer table placed after the questions, when one is present."""
    keys = {}
    def remember(number, letter):
        if number in keys and keys[number] != letter:
            keys[number] = None
        else:
            keys.setdefault(number, letter)
    for index, line in enumerate(lines):
        text = _clean(line)
        if not text:
            continue
        header = _KEY_HEADER.match(text)
        if header:
            # "Answer: B" belongs to the preceding question. It must not make
            # a later short stem such as "2. A garden ..." look like a key row.
            inline = _ANSWER_LINE.match(text)
            pairs = _pairs(header.group(1))
            if (inline and not inline.group(1).isdigit()) or (header.group(1).strip() and not pairs):
                continue
            for number, letter in _pairs(header.group(1)):
                remember(number, letter)
            for following in lines[index + 1:]:
                row = _clean(following)
                if not row or _table_noise(row):
                    continue
                if len(row) > 200:
                    break
                pairs = _pairs(row)
                if pairs and _key_row(row):
                    for number, letter in pairs:
                        remember(number, letter)
                else:
                    break
            continue
        pairs = _pairs(text)
        if len(pairs) >= 3:
            residue = _PAIR.sub("", text)
            if not re.sub(r"[\s,，;；、/|]+", "", residue):
                for number, letter in pairs:
                    remember(number, letter)
    return keys


def _looks_like_key_line(text):
    if _KEY_HEADER.match(text):
        return True
    pairs = _pairs(text)
    if len(pairs) >= 3:
        residue = _PAIR.sub("", text)
        return not re.sub(r"[\s,，;；、/|]+", "", residue)
    return False


def _entry_text(value):
    if isinstance(value, str):
        return re.sub(r"^[\-\*\u2022]\s*", "", value.strip())
    return ""


def _build_question(number, stem_lines, option_rows, language, answer, explanation=""):
    options = []
    for row in option_rows:
        text = _CHECK_MARK.sub('', row["text"]).strip()
        text = re.sub(r'\s*[（(](?:correct(?: answer)?|正确(?:答案)?|正解)[）)]\s*$', '', text, flags=re.I).strip()
        if not text:
            continue
        if len(options) >= 6 or _letter(row.get('marker', ''), 6) != LETTERS[len(options)]:
            return None  # Never silently shift B/D when an option was lost by OCR.
        options.append(text)
    if len(options) < 2 or len({o.casefold() for o in options}) != len(options):
        return None
    if not stem_lines:
        return None
    stem = _join([line.strip() for line in stem_lines if line.strip()], language).strip()
    if not stem:
        return None
    if re.search(r'(?:choose|select)\s+(?:the\s+)?(?:two|three|2|3|all)\b|all that apply|(?:二|三|2|3|２|３)つ(?:を)?選|多选|複数選択', stem, re.I):
        return None
    if re.search(r'下の図|上の図|次の図|図表|グラフ|画像|diagram|figure\s*\d|shown in the (?:graph|table|image)', stem, re.I):
        return None
    explicit = answer if isinstance(answer, str) and len(answer) == 1 and answer in LETTERS[:len(options)] else ''
    answer = explicit
    return {
        "number": number,
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": explanation or "",
        "answer_source": "imported" if explicit else "",
    }


def _parse_section(lines, language):
    """Return (body, questions, warnings) for one passage section."""
    total = len(lines)
    first = None
    for index in range(total):
        text = _clean(lines[index])
        if not text or _looks_like_key_line(text):
            continue
        start = _question_start(text)
        if not start:
            continue
        count = 0
        for following in range(index + 1, min(total, index + 16)):
            row = _clean(lines[following])
            if not row:
                continue
            if _option_start(row) or _is_bold_option(lines[following]):
                count += 1
            elif _option_space(row):
                count += 1
            elif _question_start(row):
                break
        if count >= 2:
            first = index
            break
    if first is None:
        return None, [], []

    body_lines = lines[:first]
    questions = []
    current = None
    key_map = _collect_answer_key(lines)
    warnings = []
    in_answer_table = False

    def flush():
        nonlocal current
        if current is None:
            return
        question = _build_question(
            current["number"], current["stem"], current["options"], language,
            current["answer"], current["explanation"],
        )
        if question is None:
            warnings.append(f"第 {current['number']} 题没有识别到完整选项，已跳过。")
        else:
            questions.append(question)
        current = None

    for index in range(first, total):
        raw = lines[index]
        text = _clean(raw)
        if not text or _NOISE.match(text):
            continue
        if in_answer_table:
            if _key_row(text) or _table_noise(text):
                continue
            in_answer_table = False
        if _QUESTIONS_HEADING.match(text):
            continue
        answer_match = _ANSWER_LINE.match(text)
        if answer_match and current is not None:
            tail = text[answer_match.end():]
            numbered_table = answer_match.group(1).isdigit() and re.match(r'\s*[A-Fa-fアイウエオ①-⑥]', tail)
            if not numbered_table:
                current["answer"] = _letter(answer_match.group(1), 6)
                current['explanation'] = tail.strip(' :：.。')
                continue
        if _looks_like_key_line(text):
            in_answer_table = bool(_KEY_HEADER.match(text))
            continue
        bare = _BARE_PAIR.match(text)
        if bare and (key_map or (current is not None and int(bare.group(1)) <= current["number"])):
            continue
        start = _question_start(text)
        if start:
            number, stem = start
            flush()
            current = {
                "number": number,
                "stem": [stem] if stem else [],
                "options": [],
                "answer": "",
                "explanation": "",
            }
            continue
        if current is None:
            continue
        explanation = _EXPLANATION.match(text)
        if explanation:
            current['in_explanation'] = True
            current['explanation'] = explanation[1]
            continue
        if current.get('in_explanation'):
            current['explanation'] = (current['explanation'] + ' ' + text).strip()
            continue
        option = _option_start(text)
        if option is None and not current["answer"]:
            space_option = _option_space(text)
            if space_option:
                marker = _letter(space_option[0], 6)
                expected = LETTERS[len(current["options"])] if len(current['options']) < 6 else ''
                if marker == expected:
                    option = space_option
        if option:
            current["options"].append({
                "marker": option[0],
                "text": option[1].strip(),
                "marked": _is_bold_option(raw) or bool(_CHECK_MARK.search(raw)),
            })
            continue
        if current["answer"]:
            # Text after an explicit answer is an explanation, not an option.
            current["explanation"] = (current["explanation"] + " " + text).strip()
            continue
        if current["options"]:
            current["options"][-1]["text"] += (" " if language == "en" else "") + text
        else:
            current["stem"].append(text)
    flush()

    if not questions:
        return None, [], warnings

    for question in questions:
        answer = key_map.get(question["number"])
        if question['number'] in key_map and answer is None:
            warnings.append(f"第 {question['number']} 题的答案表有冲突，留待核对。")
            question.update(answer='', answer_source='')
            continue
        if answer and question['answer'] and answer != question['answer']:
            warnings.append(f"第 {question['number']} 题的行内答案与答案表冲突，请手动核对。")
            question['answer'] = ''
            question['answer_source'] = ''
        elif answer and not question["answer"]:
            question["answer"] = _letter(answer, len(question["options"]))
            question["answer_source"] = "key"

    # Body paragraphs: keep the passage prose, drop question headings and rules.
    paragraphs, buffer = [], []
    in_keys = False
    for line in body_lines:
        text = _clean(line)
        if _KEY_HEADER.match(text):
            in_keys = True
            continue
        if in_keys and (_key_row(text) or _table_noise(text) or not text):
            continue
        in_keys = False
        if _INSTRUCTION.match(text):
            continue
        if not text or _NOISE.match(text) or _QUESTIONS_HEADING.match(text):
            if buffer:
                paragraphs.append(_join(buffer, language))
                buffer = []
            continue
        if _SECTION.match(text) and len(text) < 160:
            if buffer:
                paragraphs.append(_join(buffer, language))
                buffer = []
            continue
        if re.match(r"^.{0,40}(?:questions?)\s*$", text, re.I) and len(text) < 60:
            continue
        buffer.append(text)
    if buffer:
        paragraphs.append(_join(buffer, language))
    body = "\n\n".join(paragraphs).strip()
    return body, questions, warnings


def parse_reading_papers(raw, language, title=""):
    """Parse pasted text into one or more passage/quiz papers.

    Raises ValueError when no passage with a usable multiple-choice question is
    found, so callers can tell the user to use the intensive-reading import.
    """
    if language not in ("en", "ja"):
        raise ValueError("请选择英语或日语。")
    text = _normalize(raw)
    lines = text.split("\n")
    marks = _section_marks(lines)
    sections = []
    if marks:
        for order, (index, number, section_title) in enumerate(marks):
            end = marks[order + 1][0] if order + 1 < len(marks) else len(lines)
            sections.append((number, section_title, lines[index + 1:end]))
    else:
        sections = [(1, "", lines)]

    papers, warnings = [], []
    for number, section_title, section_lines in sections:
        body, questions, section_warnings = _parse_section(section_lines, language)
        warnings.extend(section_warnings)
        if not body or not questions:
            if section_title:
                warnings.append(f"「{section_title}」没有识别到可用题目，已跳过。")
            continue
        seen = set()
        unique = []
        duplicate = False
        for q in questions:
            if q['number'] in seen:
                warnings.append(f"重复题号 {q['number']}，请拆分文章后再识别。")
                duplicate = True
                continue
            seen.add(q['number'])
            unique.append(q)
        questions = unique
        if duplicate:
            continue  # Unknown passage boundaries must not mix two papers.
        if any(_is_bold_option(line) for line in section_lines):
            warnings.append('加粗或勾选选项不作为正确答案，请核对原书答案。')
        paper_title = section_title.strip()
        auto_title = ""
        if not paper_title:
            candidate = next((_clean(line) for line in section_lines if _clean(line)), "")
            if 0 < len(candidate) <= 120 and not re.search(r"[。！？.!?]$", candidate):
                paper_title = candidate
                auto_title = candidate
            if not paper_title:
                paper_title = title.strip() or f"阅读练习 {number}"
        if not section_title and title.strip() and len(sections) == 1:
            paper_title = title.strip()
        if len(sections) > 1 and title.strip() and not section_title:
            paper_title = f"{title.strip()} · {number}"
        if auto_title and body.startswith(auto_title):
            body = body[len(auto_title):].lstrip("\n")
            if not body.strip():
                continue
        papers.append(
            dict(
                title=paper_title[:300],
                language=language,
                body=body,
                section=section_title or "",
                questions=questions,
            )
        )

    if not papers:
        raise ValueError(
            "没有识别到“文章 + 选择题”。请确认题目使用 1. 2. 3. 编号、选项使用 A. B. C. D. "
            "（或 ア イ ウ エ），也可以改用“导入精读文章”。"
        )
    # Many exam files put one answer table after the final passage. Only bind
    # it globally when the question number is unique across the whole file;
    # repeated per-passage numbering must keep its local key association.
    from collections import Counter
    occurrences = Counter(q['number'] for p in papers for q in p['questions'])
    global_keys = _collect_answer_key(lines)
    for paper in papers:
        for question in paper['questions']:
            number = question['number']
            if occurrences[number] != 1 or number not in global_keys:
                continue
            value = global_keys[number]
            answer = _letter(value, len(question['options'])) if value else ''
            if not answer or (question['answer'] and question['answer'] != answer):
                question.update(answer='', answer_source='')
                warnings.append(f'第 {number} 题的集中答案表存在冲突或无效选项，留待处理。')
            elif not question['answer']:
                question.update(answer=answer, answer_source='key')
    return dict(papers=papers, warnings=warnings)


def ai_answer_prompt(body, questions, language):
    """Prompt used for questions whose answer is not present in the text."""
    lines = []
    for question in questions:
        lines.append(f"{question['number']}. {question['stem']}")
        for index, option in enumerate(question["options"]):
            lines.append(f"{LETTERS[index]}. {option}")
        lines.append("")
    language_name = "英语" if language == "en" else "日语"
    return (
        f"你在做{language_name}阅读选择题。只依据下面的原文作答，不引入原文之外的知识。"
        "为每一道题选出唯一正确选项，并用中文写一句简短解析；"
        "再从原文中逐字摘录一句最能支持该答案的话（必须与原文完全一致，不要改写）。"
        "只返回 JSON 对象，格式为 "
        '{"answers":[{"number":1,"answer":"B","explanation":"中文解析","quote":"原文原句"}]}。'
        "answer 只能是一个大写选项字母；如果原文不足以判断，answer 留空字符串。\n\n"
        f"【原文】\n{body}\n\n【题目】\n" + "\n".join(lines)
    )


def apply_ai_answers(payload, questions, body):
    """Validate one AI response and apply it to the parsed questions in place."""
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), list):
        raise ValueError("AI 没有返回可用的答案列表。")
    by_number = {str(question["number"]): question for question in questions}
    paragraphs = body.split("\n\n")
    applied = 0
    for item in payload["answers"]:
        if not isinstance(item, dict):
            continue
        number = str(item.get('number', '')).strip()
        question = by_number.get(number)
        if question is None or question.get('answer'):
            continue
        answer = _letter(str(item.get("answer", "")), len(question["options"]))
        if not answer:
            continue
        explanation = item.get("explanation")
        quote = item.get("quote")
        evidence = []
        if isinstance(quote, str):
            quote = quote.strip().strip('“”"')
            if len(quote) >= 8 and body.count(quote) == 1:
                for index, paragraph in enumerate(paragraphs):
                    if quote in paragraph:
                        evidence = [dict(paragraph=index + 1, quote=quote)]
                        break
        if not evidence or not isinstance(explanation, str) or not explanation.strip():
            continue
        question.update(answer=answer, answer_source='ai', explanation=explanation.strip()[:2000], evidence=evidence)
        applied += 1
    return applied
