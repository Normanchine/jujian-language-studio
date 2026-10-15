"""Check whole-essay guidance, source anchoring, and past-tense context."""

from review_guidance import organize_feedback, review_english


essay = "Last weekend, I go home. My friend don't help me. I hope next weekend is fun."


def fake_request(prompt, task, token_limit, *, careful=False):
    assert essay in prompt
    assert task == "writing" and token_limit >= 8000 and careful
    assert "过去经历" in prompt and "希望" in prompt
    return {
        "overall": "全文讲述上周的事情。",
        "context": "前两句应使用过去时，最后一句表达现在的希望。",
        "strengths": ["事件顺序清楚。"],
        "priorities": ["先统一过去经历中的动词时态。"],
        "issues": [
            {"quote": "go", "correction": "went", "reason": "上周发生的动作应使用过去式。",
             "category": "时态与一致性"},
            {"quote": "don't help", "correction": "didn't help",
             "reason": "朋友上周没有帮忙，应使用过去时否定句。", "category": "时态与一致性"},
            {"quote": "imaginary phrase", "correction": "x",
             "reason": "不存在。", "category": "语法"},
        ],
        "revised_text": "Last weekend, I went home. My friend didn't help me. I hope next weekend is fun.",
        "target_feedback": "无指定目标。",
    }


result = review_english({"text": essay, "language": "en"}, fake_request)
assert [item["quote"] for item in result["issues"]] == ["go", "don't help"]
assert result["context"].startswith("前两句")
assert "hope" in result["revisedText"]
assert organize_feedback(essay, {"issues": "not an array"})["issues"] == []
repeated = organize_feedback("I go home. We have a good day. I go back.", {"issues": [
    {"quote": "go", "correction": "went", "reason": "过去时。", "category": "时态与一致性"},
    {"quote": "ood", "correction": "x", "reason": "词内片段不应作为整词。", "category": "拼写"},
]})["issues"]
assert len(repeated) == 1 and repeated[0]["repeats"] == 2
print("whole-essay guidance and quote validation: OK")
