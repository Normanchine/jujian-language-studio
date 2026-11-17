"""Stable logical folders; media paths and learning progress never move."""
import json
from pathlib import Path
from uuid import uuid4

from core.storage import atomic_json


def read_folders(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('items'), list):
        raise ValueError('资料库文件夹记录格式不受支持，原记录已保留')
    seen = set()
    for item in data['items']:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']
                or item['id'] in seen or item.get('language') not in ('en', 'ja')
                or not isinstance(item.get('name'), str) or not item['name'].strip()):
            raise ValueError('资料库文件夹记录无效，原记录已保留')
        seen.add(item['id'])
    return data['items']


def create_folder(path: Path, language: str, name: str) -> str:
    name = name.strip()
    if language not in ('en', 'ja') or not name or len(name) > 40 or any(ord(c) < 32 for c in name):
        raise ValueError('请选择语言并填写 1–40 字的文件夹名称')
    items = read_folders(path)
    duplicate = next((i for i in items if i['language'] == language and i['name'].casefold() == name.casefold()), None)
    if duplicate:
        return duplicate['id']
    key = uuid4().hex
    atomic_json(path, dict(schema_version=1, items=items + [dict(id=key, language=language, name=name)]))
    return key
