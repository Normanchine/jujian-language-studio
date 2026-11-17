"""Native Windows transitions around the application's custom QML title bar.

Keep the caption/resizable styles needed by DWM, but give QML the full client
area via WM_NCCALCSIZE. No layered-window opacity or simulated minimize fade.
https://learn.microsoft.com/windows/win32/dwm/customframe
"""
import sys
import json
from datetime import datetime

from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QObject, Property, Qt, QTimer, Signal, Slot


class NativeFrame(QAbstractNativeEventFilter):
    def __init__(self, window, frame_changed=None):
        super().__init__()
        self.frame_changed = frame_changed
        self.hwnd = int(window.winId())
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.IsZoomed.argtypes = [wintypes.HWND]
        self.user.IsIconic.argtypes = [wintypes.HWND]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user.MonitorFromWindow.restype = wintypes.HANDLE
        self.user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        self.user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.get_style = self.user.GetWindowLongPtrW
        self.get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        self.get_style.restype = ctypes.c_ssize_t
        self.set_style = self.user.SetWindowLongPtrW
        self.set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.set_style.restype = ctypes.c_ssize_t

    def enable(self):
        # WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX.
        style = self.get_style(self.hwnd, -16)
        self.set_style(self.hwnd, -16, style | 0x00CF0000)
        # SWP_NOSIZE | NOMOVE | NOZORDER | NOACTIVATE | FRAMECHANGED.
        self.user.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0037)

    def nativeEventFilter(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0
        msg = self.wintypes.MSG.from_address(int(message))
        if msg.hWnd != self.hwnd:
            return False, 0
        # Styles and composition can reset without creating a new HWND.
        # Queue work outside the native callback so our own frame update cannot recurse.
        if msg.message in {0x007D, 0x031E, 0x031A, 0x0232}:  # STYLECHANGED, DWMCOMPOSITIONCHANGED, THEMECHANGED, EXITSIZEMOVE
            if self.frame_changed:
                self.frame_changed()
        if msg.message != 0x0083:  # WM_NCCALCSIZE
            return False, 0
        if msg.wParam and self.user.IsZoomed(self.hwnd):
            # A maximized frame extends beyond the monitor. Keep QML inside
            # the monitor's work area so its controls and taskbar stay visible.
            class MonitorInfo(self.ctypes.Structure):
                _fields_ = [("size", self.wintypes.DWORD),
                            ("monitor", self.wintypes.RECT), ("work", self.wintypes.RECT),
                            ("flags", self.wintypes.DWORD)]
            info = MonitorInfo()
            info.size = self.ctypes.sizeof(info)
            monitor = self.user.MonitorFromWindow(self.hwnd, 2)
            if self.user.GetMonitorInfoW(monitor, self.ctypes.byref(info)):
                rect = self.wintypes.RECT.from_address(msg.lParam)
                rect.left, rect.top = info.work.left, info.work.top
                rect.right, rect.bottom = info.work.right, info.work.bottom
        return True, 0


class WindowActions(QObject):
    changed = Signal()

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.window = None
        self.frame = None
        self._tray_available = False
        self._maximized = False
        self._exit_pending = False
        self._transition = 0
        self._effects_timer = QTimer(self)
        self._effects_timer.setSingleShot(True)
        self._effects_timer.setInterval(100)
        self._effects_timer.timeout.connect(self._refresh_effects)

    @Property(bool, notify=changed)
    def trayAvailable(self):
        if not self._tray_available:
            return False
        from PySide6.QtWidgets import QSystemTrayIcon
        return QSystemTrayIcon.isSystemTrayAvailable()

    def attach(self, window, tray_available):
        self.window = window
        self._tray_available = tray_available
        if sys.platform == "win32":
            self.frame = NativeFrame(window, self._queue_effects)
            self.app.installNativeEventFilter(self.frame)
            self.frame.enable()
            window.installEventFilter(self)
            window.windowStateChanged.connect(self._queue_effects)
            window.visibleChanged.connect(self._queue_effects)
            window.screenChanged.connect(self._queue_effects)
            window.windowStateChanged.connect(lambda *args: self._record('state-changed'))
            self._queue_effects()
        self._record('attached')
        self.changed.emit()

    def _sync_handle(self):
        if self.frame:
            self.frame.hwnd = int(self.window.winId())
            return self.frame.hwnd
        return 0

    def _remember_size_state(self):
        state = self.window.windowState()
        if state != Qt.WindowMinimized:
            self._maximized = state == Qt.WindowMaximized

    def _record(self, action):
        # No titles, document contents, filenames, credentials or model text.
        if not self.window:
            return
        try:
            from core.paths import DATA
            path = DATA / 'window-actions.log'
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > 512 * 1024:
                path.replace(path.with_name('window-actions.previous.log'))
            handle = int(self.window.winId())
            row = dict(time=datetime.now().isoformat(timespec='milliseconds'), action=action,
                qt_visible=self.window.isVisible(), qt_state=self.window.windowState().name,
                hwnd=handle, cached_hwnd=self.frame.hwnd if self.frame else 0)
            if self.frame:
                row.update(native_visible=bool(self.frame.user.IsWindowVisible(handle)),
                           native_minimized=bool(self.frame.user.IsIconic(handle)))
            with path.open('a', encoding='utf-8') as log:
                log.write(json.dumps(row) + '\n')
        except (OSError, RuntimeError, ValueError):
            pass  # Diagnostics must never prevent a window operation.

    @Slot(str)
    def noteClose(self, decision):
        self._record('close-' + decision)

    @Slot()
    def closeWindow(self):
        self._record('close-request')
        if self.window.close():
            self.app.quit()

    def _queue_effects(self, *args):
        self._effects_timer.start()

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() in {
            QEvent.Show, QEvent.WinIdChange, QEvent.PlatformSurface,
        }:
            if event.type() in {QEvent.Show, QEvent.WinIdChange}:
                self._sync_handle()
            self._queue_effects()
        return False

    def _refresh_effects(self):
        if not self.frame or not self.window.isVisible():
            return
        # Qt may recreate the native handle during window state transitions.
        hwnd = self._sync_handle()
        # Asking DWM for rounding alone is insufficient if caption/frame styles were removed.
        # Repair only when needed; unconditional SetWindowPos would cause repeated native events.
        if self.frame.get_style(hwnd, -16) & 0x00CF0000 != 0x00CF0000:
            self.frame.enable()
        ctypes = self.frame.ctypes
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        dwm.DwmExtendFrameIntoClientArea.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        for attribute in (2, 33):
            value = ctypes.c_int(2)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
        margins = (ctypes.c_int * 4)(1, 1, 1, 1)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

    @Slot()
    def minimize(self):
        self._record('minimize-request')
        self._remember_size_state()
        self._transition += 1
        ticket = self._transition
        if self.frame:
            handle = self._sync_handle()
            if self.frame.get_style(handle, -16) & 0x00CF0000 != 0x00CF0000:
                self.frame.enable()
            self.frame.user.ShowWindow(handle, 6)  # SW_MINIMIZE, animated by DWM.
        else:
            self.window.showMinimized()
        QTimer.singleShot(120, lambda: self._confirm_minimized(ticket))

    def _confirm_minimized(self, ticket):
        if ticket != self._transition or self._exit_pending:
            return
        handle = self._sync_handle()
        if self.window.windowState() != Qt.WindowMinimized or (self.frame and not self.frame.user.IsIconic(handle)):
            self.window.showMinimized()
        confirmed = self.window.windowState() == Qt.WindowMinimized and (
            not self.frame or self.frame.user.IsIconic(self._sync_handle()))
        self._record('minimize-confirmed' if confirmed else 'minimize-failed')

    @Slot()
    def hideToTray(self):
        self._record('tray-hide-request')
        self._remember_size_state()
        self._transition += 1
        self.window.hide()
        handle = self._sync_handle()
        # Qt can already believe it is hidden while Windows still displays it.
        # In that state QWindow.hide() is a no-op; reconcile the native window too.
        if self.frame and self.frame.user.IsWindowVisible(handle):
            self.frame.user.ShowWindow(handle, 0)  # SW_HIDE.
        confirmed = not self.window.isVisible() and (not self.frame or not self.frame.user.IsWindowVisible(handle))
        self._record('tray-hide-confirmed' if confirmed else 'tray-hide-failed')

    @Slot()
    def restore(self):
        self._record('restore-request')
        self._transition += 1
        handle = self._sync_handle()
        native_minimized = bool(self.frame and self.frame.user.IsIconic(handle))
        native_hidden = bool(self.frame and not self.frame.user.IsWindowVisible(handle))
        minimized = self.window.windowState() == Qt.WindowMinimized or native_minimized
        if self.window.isVisible() and not minimized and not native_hidden:
            pass
        elif self.frame and minimized:
            self.frame.user.ShowWindow(handle, 9)  # SW_RESTORE.
            if not self.window.isVisible():
                self.window.showMaximized() if self._maximized else self.window.showNormal()
        elif self._maximized:
            self.window.showMaximized()
        else:
            self.window.showNormal()
        if self.frame and self.window.isVisible() and not self.frame.user.IsWindowVisible(self._sync_handle()):
            # The inverse mismatch is possible too: Qt thinks it is shown while
            # the native window is hidden, so Qt's show() can also be a no-op.
            self.frame.user.ShowWindow(self.frame.hwnd, 3 if self._maximized else 1)
        self.window.raise_()
        self.window.requestActivate()
        self._queue_effects()
        confirmed = self.window.isVisible() and self.window.windowState() != Qt.WindowMinimized and (
            not self.frame or (self.frame.user.IsWindowVisible(self._sync_handle()) and not self.frame.user.IsIconic(self.frame.hwnd)))
        self._record('restore-confirmed' if confirmed else 'restore-failed')

    @Slot()
    def exit(self):
        if self._exit_pending:
            return
        self._exit_pending = True
        self._transition += 1
        self._record('exit-request')
        # Leave the native tray menu's event loop before closing a minimized window.
        QTimer.singleShot(0, self._exit)

    def _exit(self):
        self.window.setProperty("forceExit", True)
        if self.window.close():
            # Hidden/minimized windows need not emit lastWindowClosed. A successful
            # explicit Exit must also end the application event loop.
            self.app.quit()
        else:
            self._exit_pending = False
            # A save error must be visible even when Exit came from a hidden tray.
            self.restore()
