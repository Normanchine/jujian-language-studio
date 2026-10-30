"""Loopback-only Mihomo control; node changes are confined to our own listener/group."""
from __future__ import annotations

import copy
import json
import os
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, ProxyHandler, build_opener

import yaml
from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

GROUP = "Jujian-YouTube"
LISTENER = "jujian-youtube"
PORT = 17897
TEST_URL = "https://www.youtube.com/generate_204"
GROUP_TYPES = {"Selector", "URLTest", "Fallback", "LoadBalance", "Relay"}
DIRECT_TYPES = {"Direct", "Reject", "RejectDrop", "Compatible", "Pass", "DNS"}


def usable_node(name, value):
    return (value.get("type") not in GROUP_TYPES | DIRECT_TYPES
            and name not in {"DIRECT", "REJECT", "PASS", "COMPATIBLE"}
            and not re.search(r"剩余流量|套餐到期|到期时间|流量重置|官网|重置日期|Traffic|Expire|Expiry", name, re.I))


def validate_loopback(value: str, *, empty=False) -> str:
    value = value.strip().rstrip("/")
    if empty and not value:
        return ""
    try:
        p = urlparse(value)
        valid = (p.scheme == "http" and p.hostname in {"127.0.0.1", "localhost", "::1"}
                 and p.port and not p.username and not p.password and not p.path
                 and not p.query and not p.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("请填写本机 HTTP 地址，例如 http://127.0.0.1:7897。")
    return value


def local_profile() -> tuple[Path, dict]:
    base = Path(os.environ.get("APPDATA", ""))
    for folder in ("io.github.clash-verge-rev.clash-verge-rev", "io.github.clash-verge-rev.clash-verge"):
        p = base / folder / "clash-verge.yaml"
        if p.is_file():
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return p, data
    raise ValueError("未找到 Clash Verge 运行配置；请填写控制地址和密钥。")


def profile_controller(config: dict) -> str:
    address = str(config.get("external-controller") or "")
    if address.startswith(":"):
        address = "127.0.0.1" + address
    address = address.replace("0.0.0.0:", "127.0.0.1:")
    return validate_loopback("http://" + address)


class ClashClient:
    def __init__(self, settings: dict, secret: str = ""):
        self.settings = settings
        self.profile = None
        try:
            self.profile = local_profile()[1]
        except (ValueError, OSError, yaml.YAMLError):
            pass
        configured = settings.get("clash_controller", "")
        self.controller = validate_loopback(configured) if configured else (
            profile_controller(self.profile) if self.profile else "http://127.0.0.1:9090")
        try:
            if not secret and self.profile and profile_controller(self.profile) == self.controller:
                secret = str(self.profile.get("secret") or "")
        except ValueError:
            pass
        self.secret = secret

    def request(self, path: str, data=None, method="GET", timeout=8):
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = "Bearer " + self.secret
        req = Request(self.controller + path, headers=headers, method=method,
                      data=None if data is None else json.dumps(data).encode())
        try:
            # Never send controller credentials through the system proxy.
            with build_opener(ProxyHandler({})).open(req, timeout=timeout) as response:
                body = response.read(16_000_001)
                if len(body) > 16_000_000:
                    raise ValueError("Clash 接口返回过大。")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise ValueError("Clash 控制接口认证失败，请检查密钥。") from None
            raise ValueError(f"Clash 接口请求失败（HTTP {exc.code}）。") from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("无法连接 Clash 控制接口，请检查 Clash、控制地址和端口。") from None

    def proxies(self):
        return self.request("/proxies")["proxies"]

    def route_ready(self, proxies=None):
        proxies = self.proxies() if proxies is None else proxies
        group = proxies.get(GROUP, {})
        if group.get("type") != "Selector":
            return False
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return True
        except OSError:
            return False

    def members(self, proxies=None):
        proxies = self.proxies() if proxies is None else proxies
        return [n for n in proxies.get(GROUP, {}).get("all", [])
                if n in proxies and usable_node(n, proxies[n])]

    def select(self, name):
        proxies = self.proxies()
        if not self.route_ready(proxies) or name not in self.members(proxies):
            raise ValueError("专用下载通道未建立或节点已失效，请重新连接。")
        self.request("/proxies/" + quote(GROUP, safe=""), {"name": name}, "PUT")

    def delay(self, name):
        path = "/proxies/" + quote(name, safe="") + "/delay?" + urlencode(
            {"url": TEST_URL, "timeout": 4000, "expected": "204"})
        try:
            delay = self.request(path, timeout=6).get("delay", 0)
            return delay if isinstance(delay, int) and delay > 0 else None
        except ValueError:
            return None

    def measure(self, cancelled=lambda: False, progress=lambda *_: None):
        proxies = self.proxies()
        if not self.route_ready(proxies):
            raise ValueError("请先建立专用下载通道。")
        members = self.members(proxies)
        rows = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(self.delay, n): n for n in members}
            for f in as_completed(futures):
                if cancelled():
                    for future in futures:
                        future.cancel()
                    raise RuntimeError("操作已取消")
                delay = f.result()
                name = futures[f]
                rows.append({"name": name, "delay": delay or 0,
                             "tested": True,
                             "label": f"{name} · {delay} ms" if delay else f"{name} · 超时"})
                progress(len(rows), len(members))
        return sorted(rows, key=lambda v: (not v["delay"], v["delay"], v["name"]))

    def install_route(self):
        # Only a locally detected Verge profile can be safely extended. Never PATCH TUN.
        if not self.profile or profile_controller(self.profile) != self.controller:
            raise ValueError("建立专用通道需要本机 Clash Verge；其他客户端请手动配置专用组和入站。")
        proxies = self.proxies()
        if GROUP in proxies:
            if self.route_ready(proxies):
                return
            raise ValueError("专用组已存在但端口不可用，请检查 17897 端口或重载 Clash 配置。")
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                raise ValueError("17897 端口已被占用，未更改 Clash 配置。")
        except OSError:
            pass
        before = self.request("/configs")
        original = copy.deepcopy(self.profile)
        # A stale disk profile must not overwrite live mode/TUN/ports.
        for key in ("mixed-port", "port", "socks-port", "redir-port", "tproxy-port", "mode", "allow-lan", "ipv6"):
            if key in before and original.get(key, 0 if key.endswith("port") else None) != before[key]:
                raise ValueError("Clash 运行状态与配置文件不同，请先在 Clash 中重新加载当前配置再建立通道。")
        if bool((original.get("tun") or {}).get("enable")) != bool((before.get("tun") or {}).get("enable")):
            raise ValueError("TUN 运行状态与配置文件不同，已停止建立通道，保留当前 TUN。")
        payload = copy.deepcopy(original)
        # Take the complete live TUN settings rather than a potentially stale disk copy.
        payload["tun"] = {**(payload.get("tun") or {}), **before.get("tun", {})}
        inline = [p["name"] for p in payload.get("proxies", []) if p.get("name") in proxies
                  and usable_node(p["name"], proxies[p["name"]])]
        providers = list((payload.get("proxy-providers") or {}).keys())
        if not inline and not providers:
            raise ValueError("当前配置没有可用于下载的节点。")
        groups = payload.setdefault("proxy-groups", [])
        listeners = payload.setdefault("listeners", [])
        if any(g.get("name") == GROUP for g in groups) or any(l.get("name") == LISTENER for l in listeners):
            raise ValueError("配置中已有同名通道，请先检查 Clash 配置。")
        group = {"name": GROUP, "type": "select"}
        if inline:
            group["proxies"] = inline
        if providers:
            group["use"] = providers
            group["exclude-filter"] = "剩余流量|套餐到期|到期时间|流量重置|官网|重置日期|Traffic|Expire|Expiry"
        groups.append(group)
        listeners.append({"name": LISTENER, "type": "http", "listen": "127.0.0.1",
                          "port": PORT, "users": [], "proxy": GROUP})
        # Reloading a full payload is required: Mihomo PATCH does not support listeners/groups.
        self.request("/configs?force=true", {"payload": yaml.safe_dump(payload, allow_unicode=True)}, "PUT", timeout=25)
        after = self.request("/configs")
        if after.get("tun") != before.get("tun") or after.get("mode") != before.get("mode"):
            raise ValueError("Clash 加载后的 TUN 或模式与原状态不一致，请在 Clash 中检查。")
        # Restore shared selector choices if the reload reset them; never change their intended selection.
        current = self.proxies()
        for name, value in proxies.items():
            if value.get("type") == "Selector" and value.get("now") in current.get(name, {}).get("all", []):
                if current[name].get("now") != value["now"]:
                    self.request("/proxies/" + quote(name, safe=""), {"name": value["now"]}, "PUT")
            elif value.get("type") in {"URLTest", "Fallback"} and value.get("fixed") in current.get(name, {}).get("all", []):
                if current[name].get("fixed") != value["fixed"]:
                    self.request("/proxies/" + quote(name, safe=""), {"name": value["fixed"]}, "PUT")
        if not self.route_ready():
            raise ValueError("专用下载通道未就绪，请检查 Clash 日志。")


class ControlJob(QThread):
    result = Signal(dict)
    failed = Signal(str)
    message = Signal(str)
    progress = Signal(int, int)

    def __init__(self, settings, secret, action, name=""):
        super().__init__()
        self.settings, self.secret, self.action, self.name = settings, secret, action, name

    def run(self):
        try:
            client = ClashClient(self.settings, self.secret)
            if self.action == "setup":
                client.install_route()
            if self.action == "select":
                client.select(self.name)
            proxies = client.proxies()
            ready = client.route_ready(proxies)
            rows = [{"name": n, "delay": 0, "label": n, "tested": False} for n in client.members(proxies)]
            if self.action == "test":
                def progress(n, total):
                    self.message.emit(f"正在检测 YouTube 连通性 {n}/{total}…")
                    self.progress.emit(n, total)
                rows = client.measure(self.isInterruptionRequested, progress)
            self.result.emit({"ready": ready, "nodes": rows, "current": proxies.get(GROUP, {}).get("now", ""),
                              "controller": client.controller, "tested": self.action == "test"})
        except Exception as exc:
            self.failed.emit(str(exc))


class ClashBridge(QObject):
    changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._job = None
        self._nodes, self._current, self._status = [], "", ""
        self._ready = False
        self._action, self._test_progress = "", 0.0

    @Property(bool, notify=changed)
    def busy(self): return bool(self._job and self._job.isRunning())

    @Property(bool, notify=changed)
    def ready(self): return self._ready

    @Property(bool, notify=changed)
    def testing(self): return self.busy and self._action == "test"

    @Property(float, notify=changed)
    def testProgress(self): return self._test_progress

    def _set_progress(self, done, total):
        self._test_progress = done / total if total else 0
        self.changed.emit()

    @Slot()
    def cancel(self):
        if self.testing:
            self._job.requestInterruption()

    @Property(str, notify=changed)
    def current(self): return self._current

    @Property(str, notify=changed)
    def status(self): return self._status

    @Property("QVariantList", notify=changed)
    def nodes(self): return self._nodes

    def _message(self, text):
        self._status = text
        self.changed.emit()

    def _done(self, data):
        if not data["tested"]:
            previous = {n["name"]: n for n in self._nodes}
            data["nodes"] = [previous.get(n["name"], n) for n in data["nodes"]]
        self._ready, self._nodes, self._current = data["ready"], data["nodes"], data["current"]
        self._status = ("专用通道已连接。" if self._ready else "已连接 Clash；请建立专用下载通道。")
        if data["tested"]:
            self._status = f"测试完成：{sum(bool(n['delay']) for n in self._nodes)}/{len(self._nodes)} 个节点可连接 YouTube。"
        self.changed.emit()

    def _failed(self, detail):
        if detail != "操作已取消":
            self._ready = False
        self._message(detail)

    @Slot(str, str)
    def run(self, action, name=""):
        if self.busy or action not in {"refresh", "setup", "test", "select"}:
            return
        self._job = ControlJob(self.settings.values.copy(), self.settings.clashSecret(), action, name)
        self._action, self._test_progress = action, 0.0
        self._job.result.connect(self._done)
        self._job.failed.connect(self._failed)
        self._job.message.connect(self._message)
        self._job.progress.connect(self._set_progress)
        self._job.finished.connect(self.changed.emit)
        self._message("正在连接 Clash…" if action != "setup" else "正在建立专用通道，保留现有 TUN 设置…")
        self._job.start()

    def close(self):
        if self._job and self._job.isRunning():
            self._job.requestInterruption()
            self._job.wait()
