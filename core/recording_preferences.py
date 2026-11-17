"""Persistent recording defaults, independent of current capture or study data."""
import json
from pathlib import Path

from core.storage import atomic_json

DEFAULTS = dict(schema_version=1, deviceName='', padding=.5, thresholdDb=-50,
                transcribe=True, language='en')


def validate_preferences(value):
    if (not isinstance(value, dict) or value.get('schema_version') != 1
            or not isinstance(value.get('deviceName'), str)
            or type(value.get('padding')) not in (int, float) or value['padding'] not in (.5, 1)
            or type(value.get('thresholdDb')) is not int or value['thresholdDb'] not in (-60, -50, -40)
            or type(value.get('transcribe')) is not bool or value.get('language') not in ('en', 'ja')):
        raise ValueError('录制设置记录无效或版本不受支持，原文件已保留')
    return value


def read_preferences(path: Path):
    if not path.exists():
        return dict(DEFAULTS)
    return validate_preferences(json.loads(path.read_text(encoding='utf-8')))


def save_preferences(path: Path, **updates):
    value = dict(read_preferences(path), **updates)
    validate_preferences(value)
    atomic_json(path, value)
    return value
