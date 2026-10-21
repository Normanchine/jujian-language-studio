"""Writing-task catalogue. Imported material must carry a bound text review."""
import hashlib
import json
from pathlib import Path


def task_digest(row: dict) -> str:
    payload = {**row, 'review': {key:value for key,value in row.get('review', {}).items() if key != 'content_sha256'}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def imported_review_valid(row: dict) -> bool:
    review = row.get('review', {})
    sources = row.get('provenance', [])
    return (isinstance(review, dict) and review.get('status') == 'approved'
            and review.get('scope') == 'text_completeness_and_task_binding'
            and isinstance(sources, list) and bool(sources)
            and all(isinstance(s, dict) and s.get('unit_id') and s.get('candidate_id')
                    and isinstance(s.get('source'), dict) and s['source'].get('record_id')
                    and isinstance(s.get('source_text_sha256'), str) and len(s['source_text_sha256']) == 64
                    for s in sources)
            and review.get('content_sha256') == task_digest(row))


def load_tasks(path: Path, allow_demo: bool = False) -> list[dict]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    result = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if row.get("review_status") != "ready" and not (allow_demo and row.get("review_status") == "demo"):
            continue
        if row.get('bank_schema') is not None and (row['bank_schema'] != 1 or not imported_review_valid(row)):
            continue
        if (row.get("kind") in {"toefl_email", "toefl_discussion"}
                and all(isinstance(row.get(k), str) and row[k].strip()
                        for k in ("id", "set_id", "set_title", "title", "prompt", "version", "source"))
                and type(row.get("limit_seconds")) is int and 0 < row["limit_seconds"] <= 7200
                and row["id"] not in {item["id"] for item in result}):
            result.append(row)
    return result
