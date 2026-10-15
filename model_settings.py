"""Local model routing and Windows credential storage."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QUrl

import keyring
from keyring.backends.Windows import WinVaultKeyring
from PySide6.QtCore import QObject, Property, Signal, Slot

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG = ROOT / "data" / "settings.json"
KEY_SERVICE = "mainichi-nihongo-cloud-api"
KEY_USER = "default"
QWEN_KEY_USER = "aliyun-qwen"
DEFAULTS = {
    "download_dir": str(Path.home() / "Downloads" / "句间"),
    "cloud_endpoint": "",
    "cloud_model": "",
    "translation_backend": "local",
    "analysis_backend": "local",
    "writing_backend": "local",
}


def read_settings() -> dict:
    try:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, ValueError):
        raw = {}
    return {**DEFAULTS, **{key: raw[key] for key in DEFAULTS if key in raw}}


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
                "download_dir": str(folder.resolve()), "cloud_endpoint": endpoint,
                "cloud_model": model.strip(), "translation_backend": translation,
                "analysis_backend": analysis, "writing_backend": writing,
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
