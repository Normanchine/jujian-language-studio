"""Run optional, resumable sentence explanations through local Ollama."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from linguistics import display_tokens


MODEL = "qwen3-8b-nothink:latest"
TRANSLATION_MODEL = MODEL


class ModelResponseError(ValueError):
    """The model responded, but did not provide a usable analysis."""


SCHEMA = {
    "type": "object",
    "properties": {
        "grammar": {"type": "string"},
        "vocabulary": {
            "type": "array", "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "surface": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["surface", "meaning"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["grammar", "vocabulary"],
    "additionalProperties": False,
}

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
    "additionalProperties": False,
}


def validate_analysis(raw: object, source: str, language: str = "ja") -> dict:
    if not isinstance(raw, dict):
        raise ValueError("模型结果不是对象")
    grammar = str(raw.get("grammar", "")).strip()[:140]
    vocabulary = []
    entries = raw.get("vocabulary", [])
    if not isinstance(entries, list):
        entries = []
    content_tokens = [token["text"] for token in display_tokens(source, [], language)
                      if language == "en" or token["category"] in {"noun", "verb", "adjective", "adverb"}]
    for item in entries[:4]:
        if not isinstance(item, dict):
            continue
        surface = str(item.get("surface", "")).strip()
        meaning = str(item.get("meaning", "")).strip()[:45]
        useful_surface = raw.get("model") == "manual" or any(token in surface for token in content_tokens)
        if surface and surface in source and meaning and useful_surface:
            vocabulary.append({"surface": surface, "meaning": meaning})
    model = "manual" if raw.get("model") == "manual" else MODEL
    translation = str(raw.get("translation", "")).strip()[:300]
    translation_model = str(raw.get("translation_model", "")) if translation else ""
    return {"grammar": grammar, "vocabulary": vocabulary, "model": model,
            "source_text": source, "translation": translation, "translation_model": translation_model}


def translate(text: str, language: str = "ja") -> str:
    source_language = "英语" if language == "en" else "日语"
    english_note = ("英语 wish + 过去完成时表示对过去事实的遗憾，应译为‘要是当时……就好了’。"
                    if language == "en" else "")
    prompt = (
        f"你是{source_language}到简体中文的翻译助手。准确、自然地翻译下面的原句。"
        "保留原句的语气、否定、时态和不确定性；注意虚拟语气与对过去的遗憾，不能把未发生的事译成已发生；不要增添原文没有的信息。"
        + english_note
        + "只返回 JSON，其中 translation 是整句中文译文。\n原句：" + text
    )
    from model_settings import read_settings
    if read_settings()["translation_backend"] == "cloud":
        from ai_client import ask_json
        result = str(ask_json(prompt, "translation", 384).get("translation", "")).strip()
        if not result:
            raise ModelResponseError("云端模型没有返回译文")
        return result[:300]
    for attempt, token_limit in enumerate((192, 384)):
        payload = json.dumps({
            "model": TRANSLATION_MODEL, "prompt": prompt, "format": TRANSLATION_SCHEMA,
            "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": 2048, "num_predict": token_limit},
        }, ensure_ascii=False).encode("utf-8")
        request = Request("http://127.0.0.1:11434/api/generate", data=payload,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
        try:
            if result.get("done_reason") == "length":
                raise ValueError("model output reached length limit")
            translation = str(json.loads(result["response"])["translation"]).strip()
            if not translation:
                raise ValueError("empty translation")
            return translation[:300]
        except (KeyError, TypeError, ValueError) as exc:
            if attempt == 1:
                raise ModelResponseError("模型连续两次未返回有效中文译文") from exc
    raise AssertionError("unreachable")


def explain(text: str, language: str = "ja") -> dict:
    source_language = "英语" if language == "en" else "日语"
    prompt = (
        f"请只分析以下{source_language}句子，给中文母语{source_language}学习者做精听卡片。"
        "grammar 必须是一句完整中文解释，指出句中一个重要表达的构成和在本句的意思。"
        "不能仅摘录原文词语；确实没有值得说明的表达才留空。"
        "vocabulary 最多两项，surface 必须是原文连续片段，meaning 写本句中的中文意思。"
        "忽略常见助词和句尾礼貌语，不要编造。只返回符合 JSON schema 的 JSON。\n"
        f"原句：{text}"
    )
    from model_settings import read_settings
    settings = read_settings()
    if settings["analysis_backend"] == "cloud":
        from ai_client import ask_json
        analysis = validate_analysis(ask_json(prompt, "analysis", 768), text, language)
        analysis["model"] = settings["cloud_model"]
        return analysis
    for attempt, token_limit in enumerate((384, 768)):
        payload = json.dumps({
            "model": MODEL, "prompt": prompt, "format": SCHEMA,
            "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": 2048, "num_predict": token_limit},
        }, ensure_ascii=False).encode("utf-8")
        request = Request("http://127.0.0.1:11434/api/generate", data=payload,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
        try:
            if result.get("done_reason") == "length":
                raise ValueError("模型输出达到长度上限")
            return validate_analysis(json.loads(result["response"]), text, language)
        except (KeyError, TypeError, ValueError) as exc:
            if attempt == 1:
                raise ModelResponseError("模型连续两次返回不完整或无效的 JSON") from exc
    raise AssertionError("unreachable")


def main(args: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:] if args is None else args
    if len(args) != 1:
        print("usage: enrich_job.py INPUT_JSON", file=sys.stderr)
        return 2
    jobs = json.loads(Path(args[0]).read_text(encoding="utf-8"))["jobs"]
    for job in jobs:
        try:
            result = {"index": job["index"], "text": job["text"],
                      "analysis": explain(job["text"])}
        except (OSError, URLError, HTTPError, ValueError, KeyError, TimeoutError) as exc:
            result = {"index": job["index"], "error": str(exc)}
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 1
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
