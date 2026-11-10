"""Native Windows transitions around the application's custom QML title bar.

Keep the caption/resizable styles needed by DWM, but give QML the full client
area via WM_NCCALCSIZE. No layered-window opacity or simulated minimize fade.
https://learn.microsoft.com/windows/win32/dwm/customframe
"""
import sys

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
        self._effects_timer = QTimer(self)
        self._effects_timer.setSingleShot(True)
        self._effects_timer.setInterval(100)
        self._effects_timer.timeout.connect(self._refresh_effects)

    @Property(bool, notify=changed)
    def trayAvailable(self):
        return self._tray_available

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
            self._queue_effects()
        self.changed.emit()

    def _queue_effects(self, *args):
        self._effects_timer.start()

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() in {
            QEvent.Show, QEvent.WinIdChange, QEvent.PlatformSurface,
        }:
            self._queue_effects()
        return False

    def _refresh_effects(self):
        if not self.frame or not self.window.isVisible():
            return
        # Qt may recreate the native handle during window state transitions.
        hwnd = int(self.window.winId())
        if hwnd != self.frame.hwnd:
            self.frame.hwnd = hwnd
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
        self._maximized = self.window.windowState() == Qt.WindowMaximized
        if self.frame:
            self.frame.user.ShowWindow(self.frame.hwnd, 6)  # SW_MINIMIZE, animated by DWM.
        else:
            self.window.showMinimized()

    @Slot()
    def hideToTray(self):
        self._maximized = self.window.windowState() == Qt.WindowMaximized
        self.window.hide()

    @Slot()
    def restore(self):
        minimized = self.window.windowState() == Qt.WindowMinimized
        if self.window.isVisible() and not minimized:
            pass
        elif self.frame and minimized:
            self.frame.user.ShowWindow(self.frame.hwnd, 9)  # SW_RESTORE.
        elif self._maximized:
            self.window.showMaximized()
        else:
            self.window.showNormal()
        self.window.raise_()
        self.window.requestActivate()

    @Slot()
    def exit(self):
        if self._exit_pending:
            return
        self._exit_pending = True
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
