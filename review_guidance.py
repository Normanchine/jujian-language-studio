"""Whole-essay English feedback with source-quote validation."""

from __future__ import annotations

import json
import re

from ai_client import ask_json


def _short_list(value: object, limit: int, length: int = 300) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:length] for item in value[:limit] if str(item).strip()]


def organize_feedback(source: str, answer: dict) -> dict:
    """Keep teacher guidance grounded in the exact submitted essay."""
    issues = []
    seen = set()
    for item in answer.get("issues", []) if isinstance(answer.get("issues"), list) else []:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()[:240]
        correction = str(item.get("correction", "")).strip()[:300]
        reason = str(item.get("reason", "")).strip()[:600]
        if not quote or not correction or not reason:
            continue
        pattern = re.escape(quote)
        if quote[0].isalnum():
            pattern = r"(?<!\w)" + pattern
        if quote[-1].isalnum():
            pattern += r"(?!\w)"
        positions = [match.start() for match in re.finditer(pattern, source)]
        if not positions:
            continue
        if quote.casefold() == correction.casefold():
            continue
        key = (quote.casefold(), correction.casefold())
        if key in seen:
            continue
        seen.add(key)
        category = str(item.get("category", "")).strip()
        if category not in {"时态与一致性", "语法", "拼写", "用词与表达", "结构与连贯"}:
            category = "用词与表达"
        issues.append({"quote": quote, "correction": correction, "reason": reason,
                       "category": category, "position": positions[0], "repeats": len(positions)})
    issues.sort(key=lambda item: item["position"])
    for item in issues:
        del item["position"]
    return {
        "language": "en",
        "text": source,
        "overall": str(answer.get("overall", "")).strip()[:2500],
        "context": str(answer.get("context", "")).strip()[:1200],
        "strengths": _short_list(answer.get("strengths"), 4),
        "priorities": _short_list(answer.get("priorities"), 5),
        "issues": issues[:45],
        "revisedText": str(answer.get("revised_text", "")).strip()[:6000],
        "targetFeedback": str(answer.get("target_feedback", "")).strip()[:1200],
    }


def review_english(draft: dict, requester=ask_json) -> dict:
    text = str(draft.get("text", "")).strip()
    if not text:
        raise ValueError("请先写正文")
    mode = {"toefl_email": "模拟 TOEFL 邮件练习",
            "toefl_discussion": "模拟 TOEFL 学术讨论练习"}.get(
                draft.get("writing_mode"), "普通英语作文")
    prompt = (
        "你是一位严谨的英语写作老师。先通读整篇原文，确定时间线、叙述视角、作者想表达的意思，"
        "再从全文层面给出教学反馈。不要把每句单独交给不同老师，也不要凑错误数量。\n"
        "逐句重查全文，但在判断每处错误时始终考虑前后文。特别核查整篇的叙事时态、"
        "每个限定动词、主谓一致、否定句、单复数、拼写、用词、标点和衔接。"
        "参考改写还要检查逗号是否错误连接两个完整句子；必要时使用句号、分号或连词。"
        "过去经历中的动作通常用过去时；表达现在的希望或将来计划时不要强行改成过去时。\n"
        "只指出确定的问题。quote 必须逐字取自原文且是能独立理解的最短片段。"
        "如果同一个错误词在原文中出现多次，quote 要包含足够上下文以唯一定位每一处，"
        "例如分别用 I go to the park 和 I go home，不要只写 go；"
        "correction 必须是可直接替换 quote 的英文文本，不能与 quote 相同；"
        "reason 用中文解释为什么要改，说明它和全文语境的关系。"
        "不要编造词源、拼写拆解、官方评分或原文中没有的错误。"
        "如果需要补词，quote 取包含缺词位置的短语，并给出完整的替换短语。\n"
        "仅输出 JSON 对象，字段："
        "overall（中文整体点评，先说内容和主要问题）、"
        "context（中文说明全文时间线和应采用的时态）、"
        "strengths（中文优点数组）、priorities（最值得先改的中文建议数组）、"
        "issues（按原文顺序的错误数组，每项含 quote、correction、reason、category；"
        "category 只能是时态与一致性/语法/拼写/用词与表达/结构与连贯）、"
        "revised_text（保留原意和叙事时间线的完整英文参考改写）、"
        "target_feedback（针对写作目标的中文反馈）。"
        "不要在 JSON 之外输出文字。\n"
        f"任务类型：{mode}。题目：{draft.get('topic', '')}。"
        f"目标表达：{json.dumps(draft.get('targets', []), ensure_ascii=False)}。\n"
        f"完整原文：\n{text}"
    )
    answer = requester(prompt, "writing", 8000, careful=True)
    result = organize_feedback(text, answer)
    if not result["overall"] or not result["issues"] and not result["revisedText"]:
        raise ValueError("模型没有返回完整的作文指导，请重试。")
    return result
