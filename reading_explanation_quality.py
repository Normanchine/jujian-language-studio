"""Validate student-facing explanations without turning internal data into prose."""
import re

_INTERNAL = re.compile(
    r'(?<![A-Za-z0-9_])g\d+_\d+(?![A-Za-z0-9_])'
    r'|(?<![A-Za-z0-9_])(?:candidate_id|estimated_band|vocabulary_levels|level_source|start_units|end_units)(?![A-Za-z0-9_])'
    r'|(?<![A-Za-z0-9_])band\s*(?:为|是|[:=])\s*[\s\"\x27`]*(?:unknown|basic|intermediate|advanced)(?![A-Za-z0-9_])'
    r'|(?:候选(?:编号|列表|条目|标识)|最小高亮范围|(?:程序|模型)(?:已确定|选择的候选)|返回\s*JSON)',
    re.IGNORECASE,
)


def teaching_fields(item):
    """Reject the whole annotation if any displayed field is malformed or leaks metadata."""
    result = {}
    for key in ('meaning', 'connection', 'point'):
        value = item.get(key, '')
        if value is None and key != 'meaning':
            value = ''
        if not isinstance(value, str) or _INTERNAL.search(value):
            raise ValueError('语法解释包含非教学内容或格式不正确')
        result[key] = value.strip()
    if not result['meaning']:
        raise ValueError('语法解释缺少本句含义')
    return result


def saved_explanation_view(item):
    """Keep historical favorites intact on disk while hiding unreviewed AI metadata."""
    view = dict(item)
    if item.get('source') == '已更正' or item.get('manual'):
        return view
    try:
        teaching_fields(item)
    except ValueError:
        view.update(meaning='这条旧解释需要重新分析，请返回原文更新。', connection='', point='', needsReanalysis=True)
    return view
