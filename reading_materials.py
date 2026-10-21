"""Validate reviewed development reading banks separately from learning records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_bundle(raw):
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or raw.get("review_status") != "approved":
        raise ValueError("阅读材料库尚未审核或格式无效")
    papers, intensive = raw.get("papers"), raw.get("intensive_articles")
    if not isinstance(papers, list) or not isinstance(intensive, list):
        raise ValueError("阅读材料库缺少目录")
    seen = set()
    for article in [*papers, *intensive]:
        source = article.get("source", {})
        if (not article.get("id") or article["id"] in seen or not article.get("body")
                or digest(article["body"]) != source.get("body_sha256") or not source.get("reviewer")):
            raise ValueError("阅读正文或审核记录发生变化")
        seen.add(article["id"])
        if article in intensive:
            if source.get("review_status") != "intensive_only" or article.get("hasQuestions") is not False or article.get("questions"):
                raise ValueError("精读正文不能冒充计分题")
            continue
        if source.get("review_status") != "approved" or not article.get("questions"):
            raise ValueError("阅读练习未审核")
        for question in article["questions"]:
            review = question.get("review", {})
            content_hash = digest(json.dumps([question["stem"], question["options"]], ensure_ascii=False))
            if (review.get("verdict") != "approved" or not review.get("reviewer")
                    or review.get("body_sha256") != source["body_sha256"]
                    or review.get("export_content_sha256") != content_hash or not question.get("evidence")):
                raise ValueError("题目与审核内容不一致")
            provenance = question.get("provenance", [])
            if not provenance or any(p.get("answer_letter") != question.get("answer") or not p.get("evidence") for p in provenance):
                raise ValueError("题目答案缺少一致的来源证据")
    return raw


def load_bundle(path: Path):
    if not path.exists():
        return {"papers": [], "intensive_articles": []}
    return validate_bundle(json.loads(path.read_text(encoding="utf-8")))
