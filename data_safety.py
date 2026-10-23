"""Settings-facing backup and recycle-bin controls."""
import json
import threading
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from core.storage import DataStore


class DataSafetyBridge(QObject):
    changed = Signal()
    essaysRestored = Signal()
    _automaticFinished = Signal(str)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.store = DataStore(root)
        self._status = ''
        self._automatic_running = False
        self._automaticFinished.connect(self._finish_automatic)

    @Property(str, constant=True)
    def directory(self):
        return str(self.store.root)

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property('QVariantList', notify=changed)
    def snapshots(self):
        rows = []
        labels = {'manual': '手动备份', 'daily': '每日自动备份', 'before-restore': '恢复前备份'}
        for path in sorted(self.store.backups.glob('*.zip'), reverse=True):
            parts = path.stem.split('-', 3)
            if len(parts) != 4:
                label = path.stem
            else:
                try:
                    when = datetime.strptime(parts[0] + parts[1], '%Y%m%d%H%M%S')
                    kind = parts[3]
                    label = when.strftime('%m月%d日 %H:%M') + ' · ' + (
                        '每周自动备份' if kind.startswith('weekly-') else labels.get(kind, kind))
                except ValueError:
                    label = path.stem
            rows.append({'name': path.name, 'label': label})
        return rows

    @Property(bool, notify=changed)
    def restorePending(self):
        return self.store.pending.exists()

    @Property('QVariantList', notify=changed)
    def essays(self):
        rows = []
        for entry in (self.store.root / 'trash' / 'essays').glob('*'):
            try:
                info = json.loads((entry / 'entry.json').read_text(encoding='utf-8'))
                content = json.loads((entry / 'content.json').read_text(encoding='utf-8'))
                rows.append({'id': entry.name, 'title': content.get('title') or '未命名作文', 'deleted': info['deleted']})
            except (OSError, ValueError, KeyError, AttributeError):
                continue
        return sorted(rows, key=lambda x: x['deleted'], reverse=True)

    def _run(self, operation, success):
        try:
            operation()
            self._status = success
            ok = True
        except (OSError, ValueError, KeyError, BadZipFile) as exc:
            self._status = '操作失败：' + str(exc)
            ok = False
        self.changed.emit()
        return ok

    @Slot()
    def refresh(self):
        self.changed.emit()

    @Slot(result=bool)
    def backup(self):
        return self._run(self.store.snapshot, '备份已创建并校验。')

    @Slot()
    def automaticBackup(self):
        if self._automatic_running:
            return
        self._automatic_running = True

        def run():
            try:
                self.store.daily_snapshot()
                status = '当日备份已就绪（保留最近 14 份自动备份）。'
            except Exception as exc:
                status = '操作失败：' + str(exc)
            self._automaticFinished.emit(status)

        threading.Thread(target=run, name='daily-data-backup').start()

    @Slot(str)
    def _finish_automatic(self, status):
        self._automatic_running = False
        self._status = status
        self.changed.emit()

    @Slot(str, result=bool)
    def scheduleRestore(self, name):
        return self._run(lambda: self.store.schedule_restore(name), '已安排恢复；关闭并重新启动同一数据目录后生效。恢复前会备份最新记录。')

    @Slot()
    def cancelRestore(self):
        self._run(lambda: self.store.pending.unlink(missing_ok=True), '已取消恢复。')

    @Slot(str, result=bool)
    def restoreEssay(self, entry_id):
        ok = self._run(lambda: self.store.restore_essay(entry_id), '作文已恢复，可在作文库打开。')
        if ok:
            self.essaysRestored.emit()
        return ok

    @Slot()
    def openData(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root)))

    @Slot()
    def openBackups(self):
        self.store.backups.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.backups)))
