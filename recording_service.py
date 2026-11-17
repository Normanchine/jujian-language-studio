"""Qt recording workflow: isolated capture, recoverable drafts and local import."""
from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time
from uuid import uuid4

from PySide6.QtCore import (QAbstractNativeEventFilter, QCoreApplication, QObject,
                            Property, QProcess, QTimer, QUrl, Signal, Slot)

from core.paths import DATA, ROOT
from core.storage import atomic_json


class StopHotkey(QAbstractNativeEventFilter):
    """Register a system-wide STOP key only for the lifetime of a recording."""
    identifier = 0x4A52

    def __init__(self, stop):
        super().__init__()
        self.stop = stop
        self.registered = False

    def enable(self):
        if sys.platform != 'win32':
            return False
        import ctypes
        self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.identifier, 0x4006, 0x52))
        if self.registered:
            QCoreApplication.instance().installNativeEventFilter(self)
        return self.registered

    def disable(self):
        if self.registered:
            import ctypes
            ctypes.windll.user32.UnregisterHotKey(None, self.identifier)
            QCoreApplication.instance().removeNativeEventFilter(self)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if event_type in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            import ctypes
            from ctypes.wintypes import MSG
            msg = MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.identifier:
                self.stop()
                return True, 0
        return False, 0


class RecordingBridge(QObject):
    changed = Signal()
    meterChanged = Signal()
    recordingStarted = Signal()
    reviewReady = Signal()
    imported = Signal(str, bool)
    preferencesChanged = Signal()
    failed = Signal()

    def __init__(self, study):
        super().__init__(study)
        self.study = study
        self.root = DATA / 'recordings'
        self._state = 'idle'
        self._status = '录制电脑正在播放的声音，然后导入精听。'
        self._error = ''
        self._devices = []
        self._draft = {}
        self._review = {}
        self._pending = []
        self._process = None
        self._result = None
        self._buffer = b''
        self._mode = ''
        self._level = self._seconds = 0.0
        self._started = 0.0
        self._padding = .5
        self._threshold = -50
        self._import_options = {}
        self._closing = False
        self._preserve_selection = False
        self._auto_start = False
        self._preferences_error = ''
        self._preferences_status = ''
        from core.recording_preferences import read_preferences, DEFAULTS
        try:
            self._preferences = read_preferences(DATA / 'recording-settings.json')
        except (OSError, ValueError, TypeError) as exc:
            self._preferences = dict(DEFAULTS)
            self._preferences_error = str(exc)
            self._preferences_status = '无法读取录制设置：' + str(exc)
        self._hotkey = StopHotkey(self.stop)
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._tick)
        self.refreshPending()

    @Property(str, notify=changed)
    def state(self): return self._state

    @Property(str, notify=changed)
    def status(self): return self._status

    @Property(str, notify=changed)
    def error(self): return self._error

    @Property(bool, notify=changed)
    def active(self): return self._state in ('starting', 'recording', 'stopping')

    @Property(bool, notify=changed)
    def busy(self): return self._process is not None

    @Property(bool, notify=changed)
    def shortcutAvailable(self): return self._hotkey.registered

    @Property('QVariantList', notify=changed)
    def devices(self): return self._devices

    @Property('QVariantList', notify=changed)
    def pending(self): return self._pending

    @Property('QVariantMap', notify=changed)
    def draft(self): return self._draft

    @Property('QVariantMap', notify=changed)
    def review(self): return self._review

    @Property('QVariantMap', notify=preferencesChanged)
    def preferences(self): return self._preferences

    @Property(str, notify=preferencesChanged)
    def preferencesStatus(self): return self._preferences_status

    @Property(str, notify=preferencesChanged)
    def preferencesError(self): return self._preferences_error

    @Slot(str, float, int, bool, str, result=bool)
    def saveOptions(self, device_name, padding, threshold_db, transcribe, language):
        from core.recording_preferences import save_preferences
        try:
            self._preferences = save_preferences(DATA / 'recording-settings.json', deviceName=device_name,
                padding=padding, thresholdDb=threshold_db, transcribe=transcribe, language=language)
            self._preferences_error = ''
            self._preferences_status = '录制设置已保存，下次录制时使用。'
            self.preferencesChanged.emit()
            return True
        except (OSError, ValueError, TypeError) as exc:
            self._preferences_error = str(exc)
            self._preferences_status = '录制设置未保存：' + str(exc)
            self.preferencesChanged.emit()
            return False

    @Property(float, notify=meterChanged)
    def level(self): return self._level

    @Property(float, notify=meterChanged)
    def seconds(self): return self._seconds

    @Property(str, notify=changed)
    def previewUrl(self):
        return QUrl.fromLocalFile(str(self._session_dir() / 'raw.wav')).toString() if self._draft else ''

    def _session_dir(self):
        key = self._draft.get('id', '')
        if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('录音记录标识无效')
        return self.root / 'drafts' / key

    def _save_draft(self):
        atomic_json(self._session_dir() / 'session.json', self._draft)

    def _change(self, state, status, error=''):
        self._state, self._status, self._error = state, status, error
        self.changed.emit()
        if error:
            self.failed.emit()

    def _tick(self):
        if self._started:
            self._seconds = time.monotonic() - self._started
        self._level *= .8
        self.meterChanged.emit()

    def _job(self, mode, **request):
        if self._process is not None:
            raise RuntimeError('上一项录音任务尚未完成')
        job_dir = self.root / 'jobs'
        job_dir.mkdir(parents=True, exist_ok=True)
        job_file = job_dir / f'{uuid4().hex}.json'
        atomic_json(job_file, dict(mode=mode, **request))
        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments(['--recording-job', str(job_file)] if getattr(sys, 'frozen', False)
                             else [str(ROOT / 'recording_job.py'), str(job_file)])
        process.setWorkingDirectory(str(ROOT))
        self._process, self._mode, self._result, self._buffer = process, mode, None, b''
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(lambda code, status: self._finished(process, code, job_file))
        process.errorOccurred.connect(lambda error: self._process_error(process, job_file, error))
        process.start()
        self.changed.emit()
        # Covers a missing driver, blocked native API, or failed worker startup.
        timeout = 120000 if mode in ('analyze', 'export') else 12000
        QTimer.singleShot(timeout, lambda: self._timeout(process, mode))

    def _timeout(self, process, mode):
        if self._process is process and (mode != 'capture' or self._state == 'starting'):
            self._result = dict(event='error', message='音频任务响应超时，已有录音已保留，请重试')
            process.kill()

    def _process_error(self, process, job_file, error):
        if self._process is process and error == QProcess.FailedToStart:
            self._result = dict(event='error', message='录音进程启动失败：' + process.errorString())
            self._finished(process, 1, job_file)

    def _read_output(self):
        if not self._process:
            return
        self._buffer += bytes(self._process.readAllStandardOutput())
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            try:
                message = json.loads(line.decode('utf-8'))
            except (UnicodeError, ValueError):
                continue
            event = message.get('event')
            if event == 'level':
                self._level = message['level']
                self.meterChanged.emit()
            elif event == 'started':
                self._draft['device'] = message['device']['label']
                if self._state != 'stopping':
                    self._started = time.monotonic()
                    self._hotkey.enable()
                    self._timer.start()
                    self._change('recording', '正在录制电脑声音，可以切换到刷题系统播放音频。')
                    self.recordingStarted.emit()
            else:
                self._result = message

    def _finished(self, process, code, job_file):
        if self._process is not process:
            return
        self._read_output()
        result, mode = self._result, self._mode
        detail = bytes(process.readAllStandardError()).decode('utf-8', 'replace')[-500:]
        self._process = None
        process.deleteLater()
        job_file.unlink(missing_ok=True)
        if self._closing:
            return
        if mode == 'capture':
            self._hotkey.disable()
            self._timer.stop()
            self._started = 0
            self._level = 0
            self.meterChanged.emit()
        try:
            if code or not result or result.get('event') == 'error':
                raise OSError((result or {}).get('message') or detail or '录音任务意外结束，已有录音已保留')
            if mode == 'devices':
                self._devices = result['items']
                if not self._devices:
                    raise ValueError('未找到可录制的播放设备，请连接耳机或扬声器后刷新')
                should_start, self._auto_start = self._auto_start, False
                self._change('review' if self._review else 'idle', '播放设备已更新。')
                if should_start:
                    self._start_from_preferences()
            elif mode == 'capture':
                self._draft['status'] = 'pending'
                self._save_draft()
                self.refreshPending()
                self.analyze(self._padding, self._threshold)
            elif mode == 'analyze':
                self._review = {k: v for k, v in result.items() if k != 'event'}
                if not self._preserve_selection:
                    self._draft.pop('selection', None)
                self._draft.update(analysis=self._review, status='pending')
                self._save_draft()
                self._change('review', '首尾静音已整理。试听确认后，命名并导入资料库。')
                self.reviewReady.emit()
            elif mode == 'export':
                options = self._import_options
                project = self.study.registerRecording(result['path'], options['name'], options['language'],
                    options['folder'], dict(id=self._draft['id'], device=self._draft.get('device', ''),
                        raw_path=str(self._session_dir() / 'raw.wav'),
                        start=options['start'], end=options['end'], created=self._draft['created']))
                self._draft.update(status='imported', project=project)
                self._save_draft()
                self._review = {}
                self.refreshPending()
                self._change('idle', '录音已加入资料库。')
                self.imported.emit(project, options['transcribe'])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._auto_start = False
            self.refreshPending()
            self._change('error', '操作未完成，已有录音已暂存，可以重新处理。', str(exc))

    @Slot()
    def refreshDevices(self):
        if self.busy:
            return
        self._change('devices', '正在读取播放设备…')
        try:
            self._job('devices')
        except (OSError, ValueError, RuntimeError) as exc:
            self._auto_start = False
            self._change('error', '无法读取播放设备。', str(exc))

    @Slot()
    def startConfigured(self):
        if self.busy or self.study.busy or self.study.enriching:
            return
        if self._preferences_error:
            self._change('error', '请先在设置中检查录制选项。', self._preferences_error)
            return
        # Re-enumerate for every new take: the default endpoint can change when
        # headphones are connected. A pinned, missing device must not fall back.
        self._auto_start = True
        self.refreshDevices()

    def _start_from_preferences(self):
        preferred = self._preferences['deviceName']
        index = next((i for i, d in enumerate(self._devices)
                      if d['name'] == preferred), -1) if preferred else next(
                          (i for i, d in enumerate(self._devices) if d.get('default')), -1)
        if index < 0:
            self._change('error', '没有开始录制。', '所选播放设备已断开，请到“设置 → 录制导入”重新选择。')
            return
        self._threshold = self._preferences['thresholdDb']
        self.start(index, self._preferences['padding'])

    @Slot()
    def refreshPending(self):
        pending = []
        for path in (self.root / 'drafts').glob('*/session.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if (record.get('schema_version') == 1 and record.get('status') != 'imported'
                        and record.get('id') == path.parent.name and (path.parent / 'raw.wav').is_file()):
                    pending.append(dict(id=record['id'], name=record.get('name', '暂存录音'),
                                        created=record.get('created', '')))
            except (OSError, ValueError, TypeError):
                continue
        self._pending = sorted(pending, key=lambda r: r['created'], reverse=True)
        self.changed.emit()

    @Slot(int, float)
    def start(self, device_index, padding):
        if self.busy or self.study.busy or self.study.enriching:
            return
        if device_index < 0 or device_index >= len(self._devices) or padding not in (.5, 1.0):
            self._change('error', '请选择播放设备。', '播放设备或静音设置无效')
            return
        try:
            self._padding = padding
            self._review = {}
            self._seconds = self._level = 0
            self._draft = dict(schema_version=1, id=uuid4().hex, status='pending', language=self._preferences['language'], folder='',
                               name='电脑录音 ' + datetime.now().strftime('%m-%d %H.%M'),
                               device=self._devices[device_index]['label'],
                               created=datetime.now().isoformat(timespec='seconds'))
            self._save_draft()
            self._change('starting', '正在准备录音，请等到红色录制指示出现后播放…')
            self._job('capture', path=str(self._session_dir() / 'raw.wav'), device=self._devices[device_index])
        except (OSError, ValueError, RuntimeError) as exc:
            self._change('error', '录音启动失败。', str(exc))

    @Slot()
    def stop(self):
        if not self._process or not self.active or self._state == 'stopping':
            return
        self._hotkey.disable()
        self._change('stopping', '正在保存录音并整理首尾静音…')
        self._process.write(b'stop\n')
        process = self._process
        QTimer.singleShot(6000, lambda: self._stop_timeout(process))

    def _stop_timeout(self, process):
        if self._process is process and self._state == 'stopping':
            self._result = dict(event='error', message='设备停止响应，录音已暂存。请重新处理暂存录音')
            process.kill()

    @Slot(float, int)
    def analyze(self, padding=.5, threshold_db=-50, preserve_selection=False):
        if self.busy or not self._draft:
            return
        try:
            self._padding, self._threshold = padding, threshold_db
            self._preserve_selection = preserve_selection
            self._change('processing', '正在检查音轨和首尾静音…')
            self._job('analyze', path=str(self._session_dir() / 'raw.wav'), padding=padding, thresholdDb=threshold_db)
        except (OSError, ValueError, RuntimeError) as exc:
            self._change('error', '音频处理未完成。', str(exc))

    @Slot(str)
    def recover(self, key):
        if self.busy or not any(r['id'] == key for r in self._pending):
            return
        try:
            path = self.root / 'drafts' / key / 'session.json'
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('schema_version') != 1 or record.get('id') != key:
                raise ValueError('暂存录音记录无效')
            self._draft, self._review = record, {}
            previous = record.get('analysis', {})
            padding = previous.get('padding', .5)
            threshold = previous.get('thresholdDb', -50)
            self.analyze(padding if padding in (.5, 1) else .5,
                         threshold if threshold in (-60, -50, -40) else -50, True)
        except (OSError, ValueError) as exc:
            self._change('error', '无法恢复暂存录音。', str(exc))

    @Slot(str, str, str)
    @Slot(str, str, str, float, float)
    def saveDetails(self, name, language, folder, start=None, end=None):
        if not self._draft or self._draft.get('status') == 'imported' or self.busy:
            return
        self._draft.update(name=name.strip()[:120], language=language, folder=folder)
        if (start is not None and end is not None and math.isfinite(start) and math.isfinite(end)
                and 0 <= start < end <= self._review.get('duration', 0) + .002):
            self._draft['selection'] = dict(start=start, end=end)
        try:
            self._save_draft()
        except (OSError, ValueError) as exc:
            self._change('error', '录音信息暂存失败，原音频仍保留。', str(exc))

    @Slot(str, str, str, float, float, bool)
    def importRecording(self, name, language, folder, start, end, transcribe):
        if self.busy or not self._review or self.study.busy or self.study.enriching:
            return
        try:
            if not name.strip() or len(name.strip()) > 120 or language not in ('en', 'ja'):
                raise ValueError('请填写名称并选择英语或日语')
            self.study.validateRecordingFolder(language, folder)
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or end > self._review['duration'] + .002:
                raise ValueError('裁剪范围无效，请检查起点和终点')
            self.saveDetails(name, language, folder)
            self._import_options = dict(name=name.strip(), language=language, folder=folder,
                                        start=start, end=end, transcribe=transcribe)
            target = self.root / 'media' / (self._draft['id'] + '.wav')
            # A crash between project registration and the draft acknowledgement
            # must never let a retry replace audio already used by study records.
            existing = self.study._project_path(target)
            if existing.exists():
                record = json.loads(existing.read_text(encoding='utf-8'))
                if record.get('recording', {}).get('id') != self._draft['id'] or not target.is_file():
                    raise ValueError('该录音已有其他学习记录或文件缺失，已阻止覆盖')
                self._draft.update(status='imported', project=str(existing))
                self._save_draft()
                self._review = {}
                self.refreshPending()
                self._change('idle', '该录音已经加入资料库，已打开已有记录。')
                self.imported.emit(str(existing), False)
                return
            self._change('importing', '正在保存音频并加入资料库…')
            self._job('export', path=str(self._session_dir() / 'raw.wav'),
                      target=str(target), start=start, end=end)
        except (OSError, ValueError, RuntimeError) as exc:
            self._change('error', '导入未完成，原录音已保留。', str(exc))

    @Slot()
    def newRecording(self):
        if self.busy:
            return
        self._draft, self._review = {}, {}
        self.refreshPending()
        self._change('idle', '上一条录音已暂存，可以开始新的录制。')

    def close(self):
        self._closing = True
        self._hotkey.disable()
        self._timer.stop()
        if self._process:
            self._process.write(b'stop\n')
            if not self._process.waitForFinished(2500):
                self._process.kill()
                self._process.waitForFinished(1000)
