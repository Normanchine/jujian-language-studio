"""Local model routing and Windows credential storage."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QUrl
from PySide6.QtGui import QKeySequence
from reading_gesture import normalize_trigger, MODIFIER_NAMES

import keyring
from keyring.backends.Windows import WinVaultKeyring
from PySide6.QtCore import QObject, Property, Signal, Slot

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG = ROOT / "data" / "settings.json"
KEY_SERVICE = "mainichi-nihongo-cloud-api"
KEY_USER = "default"
QWEN_KEY_USER = "aliyun-qwen"
THEME_PALETTES = {
    "sage": {"name": "松绿", "side": "#C9DDCE", "page": "#EFF5F0", "surface": "#FAFCFA",
             "accent": "#4E8068", "selection": "#E0EEE3"},
    "blue": {"name": "雾蓝", "side": "#C9DCEB", "page": "#F0F6FA", "surface": "#FAFCFD",
             "accent": "#4E7FA1", "selection": "#DFEBF3"},
    "violet": {"name": "淡紫", "side": "#D9D1E6", "page": "#F5F2F8", "surface": "#FCFBFD",
               "accent": "#806AA0", "selection": "#EBE5F2"},
    "warm": {"name": "暖棕", "side": "#E1D6CC", "page": "#F8F4F0", "surface": "#FDFBF9",
             "accent": "#A47958", "selection": "#F0E6DC"},
    "teal": {"name": "湖青", "side": "#BDDAD8", "page": "#EDF6F5", "surface": "#FBFDFD",
             "accent": "#397F7C", "selection": "#DCECEA"},
    "gold": {"name": "杏黄", "side": "#E8DDBD", "page": "#FAF7EB", "surface": "#FEFDF8",
             "accent": "#9A783B", "selection": "#F2EBD5"},
    "slate": {"name": "石板蓝", "side": "#CDD5DF", "page": "#F0F3F6", "surface": "#FBFCFD",
              "accent": "#647A96", "selection": "#E2E9F0"},
    "classic": {"name": "经典浅色", "side": "#E1E6E1", "page": "#F2F4F1", "surface": "#FFFFFF",
                "accent": "#C94859", "selection": "#E8ECE7"},
}
THEMES = set(THEME_PALETTES)
DEFAULTS = {
    "download_dir": str(Path.home() / "Downloads" / "句间"),
    "cloud_endpoint": "",
    "cloud_model": "",
    "translation_backend": "cloud",
    "analysis_backend": "cloud",
    "writing_backend": "cloud",
    "theme": "sage",
    "shortcut_previous": "Ctrl+Left",
    "shortcut_next": "Ctrl+Right",
    "shortcut_play": "Space",
    "shortcut_loop": "Ctrl+L",
    "shortcut_replay": "Ctrl+R",
    "shortcut_reading_query": "Alt",
    "video_size": "small",
    "show_transcript": False,
    "highlight_delay_ms": 200,
    "listening_video_height": 360,
}


def read_settings() -> dict:
    try:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, ValueError):
        raw = {}
    result = {**DEFAULTS, **{key: raw[key] for key in DEFAULTS if key in raw}}
    if not isinstance(result["theme"], str) or result["theme"] not in THEMES:
        result["theme"] = DEFAULTS["theme"]
    try:result["shortcut_reading_query"]=normalize_trigger(result["shortcut_reading_query"])
    except ValueError:result["shortcut_reading_query"]="Alt"
    return result


def is_qwen_endpoint(endpoint: str) -> bool:
    host = (urlparse(endpoint).hostname or "").lower()
    return host == "dashscope.aliyuncs.com" or host.endswith(".maas.aliyuncs.com")


def credential_user(endpoint: str) -> str:
    return QWEN_KEY_USER if is_qwen_endpoint(endpoint) else KEY_USER


def cloud_key(endpoint: str = "") -> str:
    vault = keyring.get_keyring()
    if not isinstance(vault, WinVaultKeyring):
        raise RuntimeError("Windows 凭据管理器不可用")
    return vault.get_password(KEY_SERVICE, credential_user(endpoint)) or ""


class SettingsBridge(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._data = read_settings()
        self._status = ""

    @Property("QVariantMap", notify=changed)
    def values(self) -> dict:
        return self._data

    @Property("QVariantMap", notify=changed)
    def palette(self) -> dict:
        return THEME_PALETTES[self._data["theme"]]

    @Property("QVariantList", constant=True)
    def themeOptions(self) -> list[dict]:
        return [{"key": key, **palette} for key, palette in THEME_PALETTES.items()]

    @Property(bool, notify=changed)
    def hasKey(self) -> bool:
        try:
            return bool(cloud_key(self._data["cloud_endpoint"]))
        except RuntimeError:
            return False

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Slot(str, result=str)
    def localFolder(self, url: str) -> str:
        return QUrl(url).toLocalFile() or url

    @Slot(str, str, str, str, str, str, result=bool)
    def save(self, download_dir: str, endpoint: str, model: str,
             translation: str, analysis: str, writing: str) -> bool:
        endpoint = endpoint.strip().rstrip("/")
        if endpoint:
            url = urlparse(endpoint)
            if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}):
                self._status = "云端接口须使用 HTTPS；本机地址可使用 HTTP。"
                self.changed.emit()
                return False
        if any(route not in {"local", "cloud"} for route in (translation, analysis, writing)):
            return False
        folder = Path(download_dir.strip()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self._data = {
                **self._data,
                "download_dir": str(folder.resolve()), "cloud_endpoint": endpoint,
                "cloud_model": model.strip(), "translation_backend": translation,
                "analysis_backend": analysis, "writing_backend": writing,
                "theme": self._data["theme"],
            }
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(CONFIG)
            self._status = "设置已保存。"
            self.changed.emit()
            return True
        except OSError as exc:
            self._status = f"保存设置失败：{exc}"
            self.changed.emit()
            return False

    @Slot(str, result=bool)
    def setTheme(self, theme: str) -> bool:
        if theme not in THEMES:
            return False
        previous = self._data
        self._data = {**previous, "theme": theme}
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(CONFIG)
        except OSError as exc:
            self._data = previous
            self._status = f"保存主题失败：{exc}"
            self.changed.emit()
            return False
        self._status = "主题已切换。"
        self.changed.emit()
        return True

    @Slot(int, int, result=str)
    def keySequence(self, key: int, modifiers: int) -> str:
        if key in (0x01000020, 0x01000021, 0x01000022, 0x01000023, 0x01000024):
            return ""
        return QKeySequence(key | (modifiers & 0x1E000000)).toString(QKeySequence.PortableText)

    def _save_preferences(self, updates: dict) -> bool:
        previous = self._data
        self._data = {**previous, **updates}
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(CONFIG)
        except OSError as exc:
            self._data = previous
            self._status = f"保存设置失败：{exc}"
            self.changed.emit()
            return False
        self._status = "设置已保存。"
        self.changed.emit()
        return True

    @Slot(str, str, str, str, str, result=bool)
    def saveShortcuts(self, previous: str, following: str, play: str, loop: str, replay: str = "Ctrl+R") -> bool:
        sequences = [QKeySequence(value).toString(QKeySequence.PortableText)
                     for value in (previous, following, play, loop, replay)]
        if any(not value for value in sequences) or len(set(sequences)) != 5:
            self._status = "快捷键不能为空或重复，请重新录入。"
            self.changed.emit()
            return False
        return self._save_preferences(dict(zip(
            ("shortcut_previous", "shortcut_next", "shortcut_play", "shortcut_loop", "shortcut_replay"), sequences)))

    @Slot(str, bool, result=bool)
    def saveListeningLayout(self, size: str, transcript: bool) -> bool:
        if size not in {"small", "medium", "large", "hidden"}:
            return False
        return self._save_preferences({"video_size": size, "show_transcript": transcript})

    @Slot(int,int,result=str)
    def readingTriggerSequence(self,key,modifiers):
        for name,code in MODIFIER_NAMES.items():
            if key==code:return name
        try:return normalize_trigger(self.keySequence(key,modifiers))
        except ValueError:return ''

    @Slot(str,result=bool)
    def saveReadingShortcut(self,value):
        try:value=normalize_trigger(value)
        except ValueError as exc:
            self._status=str(exc);self.changed.emit();return False
        return self._save_preferences({'shortcut_reading_query':value})

    @Slot(str, result=bool)
    def saveKey(self, value: str) -> bool:
        if not value.strip():
            self._status = "密钥不能为空。"
            self.changed.emit()
            return False
        try:
            vault = keyring.get_keyring()
            if not isinstance(vault, WinVaultKeyring):
                raise RuntimeError("Windows 凭据管理器不可用")
            vault.set_password(KEY_SERVICE, credential_user(self._data["cloud_endpoint"]), value.strip())
            self._status = "API Key 已保存到 Windows 凭据管理器。"
            self.changed.emit()
            return True
        except (RuntimeError, OSError) as exc:
            self._status = f"保存密钥失败：{exc}"
            self.changed.emit()
            return False

    @Slot(int, int, result=bool)
    def savePlayerPreferences(self, delay: int, height: int) -> bool:
        if delay not in {0, 100, 200, 300, 400, 600} or not 100 <= height <= 800:
            return False
        return self._save_preferences({"highlight_delay_ms": delay, "listening_video_height": height})

    @Slot()
    def clearKey(self) -> None:
        try:
            vault = keyring.get_keyring()
            if not isinstance(vault, WinVaultKeyring):
                raise RuntimeError("Windows 凭据管理器不可用")
            vault.delete_password(KEY_SERVICE, credential_user(self._data["cloud_endpoint"]))
            self._status = "API Key 已移除。"
        except keyring.errors.PasswordDeleteError:
            self._status = "未保存 API Key。"
        except (RuntimeError, OSError) as exc:
            self._status = f"移除密钥失败：{exc}"
        self.changed.emit()
