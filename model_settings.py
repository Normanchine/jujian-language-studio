"""Local model routing and Windows credential storage."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QUrl
from PySide6.QtGui import QKeySequence
from reading_gesture import normalize_trigger, MODIFIER_NAMES

from PySide6.QtCore import QObject, Property, Signal, Slot

from core.paths import ROOT, DATA
from core.storage import atomic_json
from data_safety import DataSafetyBridge
CONFIG = DATA / "settings.json"
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
    "rose": {"name": "樱粉", "side": "#ECD3DE", "page": "#FBF3F7", "surface": "#FFFAFC",
             "accent": "#A14F70", "selection": "#F5E2EB"},
    "coral": {"name": "珊瑚", "side": "#EED2C8", "page": "#FCF3EE", "surface": "#FFFBF8",
              "accent": "#A75844", "selection": "#F7E2D9"},
    "mint": {"name": "薄荷", "side": "#C4E3D8", "page": "#EDF9F4", "surface": "#F9FFFC",
             "accent": "#357C65", "selection": "#D7F0E5"},
    "olive": {"name": "橄榄", "side": "#DCE0BF", "page": "#F6F8EC", "surface": "#FDFEF8",
              "accent": "#6D7936", "selection": "#E9EDCF"},
    "indigo": {"name": "靛青", "side": "#CFD3EA", "page": "#F1F2FB", "surface": "#FCFCFF",
               "accent": "#626AA4", "selection": "#E1E4F5"},
    "silver": {"name": "银灰", "side": "#D9DFE0", "page": "#F3F6F6", "surface": "#FCFEFE",
               "accent": "#60797C", "selection": "#E3EBEC"},
}
THEMES = set(THEME_PALETTES)
DEFAULTS = {
    "download_dir": str(Path.home() / "Downloads" / "句间"),
    "youtube_proxy": "http://127.0.0.1:7897",
    "clash_controller": "",
    "youtube_auto_node": False,
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
    "shortcut_copy": "Ctrl+Shift+C",
    "close_behavior": "exit",
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
    if result["close_behavior"] not in ("exit", "tray"):
        result["close_behavior"] = "exit"
    try:result["shortcut_reading_query"]=normalize_trigger(result["shortcut_reading_query"])
    except ValueError:result["shortcut_reading_query"]="Alt"
    return result


def is_qwen_endpoint(endpoint: str) -> bool:
    host = (urlparse(endpoint).hostname or "").lower()
    return host == "dashscope.aliyuncs.com" or host.endswith(".maas.aliyuncs.com")


def credential_user(endpoint: str) -> str:
    return QWEN_KEY_USER if is_qwen_endpoint(endpoint) else KEY_USER


def cloud_key(endpoint: str = "") -> str:
    import keyring
    from keyring.backends.Windows import WinVaultKeyring
    vault = keyring.get_keyring()
    if not isinstance(vault, WinVaultKeyring):
        raise RuntimeError("Windows 凭据管理器不可用")
    return vault.get_password(KEY_SERVICE, credential_user(endpoint)) or ""


class SettingsBridge(QObject):
    changed = Signal()
    keyStatusChanged = Signal()
    _keyStatusReady = Signal(int, bool)

    def __init__(self) -> None:
        super().__init__()
        self._data = read_settings()
        self._status = ""
        self._safety = DataSafetyBridge(CONFIG.parent, self)
        self._has_key = False
        self._key_status_loading = False
        self._key_status_revision = 0
        self._keyStatusReady.connect(self._finish_key_status)

    @Property(QObject, constant=True)
    def dataSafety(self):
        return self._safety

    @Property("QVariantMap", notify=changed)
    def values(self) -> dict:
        return self._data

    @Property("QVariantMap", notify=changed)
    def palette(self) -> dict:
        return THEME_PALETTES[self._data["theme"]]

    @Property("QVariantList", constant=True)
    def themeOptions(self) -> list[dict]:
        return [{"key": key, **palette} for key, palette in THEME_PALETTES.items()]

    @Property(bool, notify=keyStatusChanged)
    def hasKey(self) -> bool:
        return self._has_key

    @Property(bool, notify=keyStatusChanged)
    def keyStatusLoading(self) -> bool:
        return self._key_status_loading

    @Slot()
    def refreshKeyStatus(self) -> None:
        if self._key_status_loading:
            return
        self._key_status_revision += 1
        revision = self._key_status_revision
        endpoint = self._data["cloud_endpoint"]
        self._key_status_loading = True
        self.keyStatusChanged.emit()

        def run():
            try:
                present = bool(cloud_key(endpoint))
            except Exception:
                present = False
            try:
                self._keyStatusReady.emit(revision, present)
            except RuntimeError:
                pass  # The application may have closed during the vault query.

        threading.Thread(target=run, daemon=True, name='settings-key-status').start()

    @Slot(int, bool)
    def _finish_key_status(self, revision: int, present: bool) -> None:
        if revision != self._key_status_revision:
            return
        self._has_key = present
        self._key_status_loading = False
        self.keyStatusChanged.emit()

    def _set_key_status(self, present: bool) -> None:
        # A completed read for a previous endpoint/save must never replace new state.
        self._key_status_revision += 1
        self._has_key = present
        self._key_status_loading = False
        self.keyStatusChanged.emit()

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
        previous = self._data
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
            atomic_json(CONFIG, self._data)
            self._status = "设置已保存。"
            if credential_user(previous["cloud_endpoint"]) != credential_user(endpoint):
                self._set_key_status(False)
                self.refreshKeyStatus()
            self.changed.emit()
            return True
        except OSError as exc:
            self._data = previous
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
            atomic_json(CONFIG, self._data)
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
            atomic_json(CONFIG, self._data)
        except OSError as exc:
            self._data = previous
            self._status = f"保存设置失败：{exc}"
            self.changed.emit()
            return False
        self._status = "设置已保存。"
        self.changed.emit()
        return True

    def clashSecret(self) -> str:
        import keyring
        from keyring.backends.Windows import WinVaultKeyring
        try:
            vault = keyring.get_keyring()
            if isinstance(vault, WinVaultKeyring):
                return vault.get_password(KEY_SERVICE, "clash-controller") or ""
        except Exception:
            pass
        return ""

    @Slot(str, str, str, bool, result=bool)
    def saveDownloadNetwork(self, proxy: str, controller: str, secret: str, automatic: bool) -> bool:
        import keyring
        from keyring.backends.Windows import WinVaultKeyring
        from clash_service import validate_loopback
        try:
            proxy = validate_loopback(proxy)
            controller = validate_loopback(controller, empty=True)
            if secret:
                vault = keyring.get_keyring()
                if not isinstance(vault, WinVaultKeyring):
                    raise ValueError("Windows 凭据管理器不可用，未保存控制密钥。")
                vault.set_password(KEY_SERVICE, "clash-controller", secret.strip())
            elif controller != self._data["clash_controller"]:
                vault = keyring.get_keyring()
                if isinstance(vault, WinVaultKeyring) and vault.get_password(KEY_SERVICE, "clash-controller"):
                    vault.delete_password(KEY_SERVICE, "clash-controller")
            return self._save_preferences({"youtube_proxy": proxy, "clash_controller": controller,
                                           "youtube_auto_node": automatic})
        except Exception as exc:
            self._status = f"代理设置未保存：{exc}"
            self.changed.emit()
            return False

    @Slot(str, str, str, str, str, result=bool)
    @Slot(str, str, str, str, str, str, result=bool)
    def saveShortcuts(self, previous: str, following: str, play: str, loop: str, replay: str = "Ctrl+R", copy: str | None = None) -> bool:
        sequences = [QKeySequence(value).toString(QKeySequence.PortableText)
                     for value in (previous, following, play, loop, replay, copy if copy is not None else self._data["shortcut_copy"])]
        if any(not value for value in sequences) or len(set(sequences)) != 6:
            self._status = "快捷键不能为空或重复，请重新录入。"
            self.changed.emit()
            return False
        return self._save_preferences(dict(zip(
            ("shortcut_previous", "shortcut_next", "shortcut_play", "shortcut_loop", "shortcut_replay", "shortcut_copy"), sequences)))

    @Slot(str, result=bool)
    def saveCloseBehavior(self, behavior: str) -> bool:
        return behavior in ("exit", "tray") and self._save_preferences({"close_behavior": behavior})

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
        import keyring
        from keyring.backends.Windows import WinVaultKeyring
        if not value.strip():
            self._status = "密钥不能为空。"
            self.changed.emit()
            return False
        try:
            vault = keyring.get_keyring()
            if not isinstance(vault, WinVaultKeyring):
                raise RuntimeError("Windows 凭据管理器不可用")
            vault.set_password(KEY_SERVICE, credential_user(self._data["cloud_endpoint"]), value.strip())
            self._set_key_status(True)
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
        import keyring
        from keyring.backends.Windows import WinVaultKeyring
        try:
            vault = keyring.get_keyring()
            if not isinstance(vault, WinVaultKeyring):
                raise RuntimeError("Windows 凭据管理器不可用")
            vault.delete_password(KEY_SERVICE, credential_user(self._data["cloud_endpoint"]))
            self._set_key_status(False)
            self._status = "API Key 已移除。"
        except keyring.errors.PasswordDeleteError:
            self._set_key_status(False)
            self._status = "未保存 API Key。"
        except (RuntimeError, OSError) as exc:
            self._status = f"移除密钥失败：{exc}"
        self.changed.emit()
