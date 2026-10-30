"""Isolated real-QML integration, no cloud calls or personal material access."""
import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temporary = tempfile.TemporaryDirectory()
os.environ['JUJIAN_DATA_DIR'] = str(Path(temporary.name) / 'data')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'

from PySide6.QtCore import QUrl, QMetaObject, Qt, QLockFile
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtCore import QObject
from core.paths import ROOT, DATA
from core.storage import DataStore
from model_settings import SettingsBridge
from writing import WritingBridge
from reading import ReadingBridge
from study import StudyBridge
from download_service import DownloadBridge

app = QApplication([])
settings = SettingsBridge()
writer = WritingBridge()
reading = ReadingBridge(DATA / 'reading')
study = StudyBridge()
downloads = DownloadBridge()
settings.dataSafety.essaysRestored.connect(writer.refresh)
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda values: warnings.extend(v.toString() for v in values))
for name, value in dict(settings=settings, writer=writer, reading=reading, study=study, downloads=downloads).items():
    engine.rootContext().setContextProperty(name, value)
engine.rootContext().setContextProperty('uiAnimationsEnabled', False)
engine.load(QUrl.fromLocalFile(str(ROOT / 'qml/Main.qml')))
assert engine.rootObjects(), warnings
window = engine.rootObjects()[0]
window.setProperty('page', 'settings')
app.processEvents()

writer.newDraft('en')
assert writer.saveDraft('Regression', 'topic', 'Original text.')
essay = Path(writer.currentPath)
before = essay.read_bytes()
with patch('writing.atomic_json', side_effect=OSError('simulated disk failure')):
    assert not writer.saveDraft('Regression', 'topic', 'Unsaved text.')
    assert writer.saveError and writer.current['text'] == 'Unsaved text.'
    writer.newDraft('ja')
    assert writer.currentPath == str(essay)
    # The close handler must refuse closure even when the writing page is hidden.
    window.close()
    app.processEvents()
    assert window.isVisible(), 'save failure must block close'
assert essay.read_bytes() == before
assert writer.retrySave()
QMetaObject.invokeMethod(window.findChild(QObject, 'saveFailureDialog'), 'close')
assert not writer.saveError
assert json.loads(essay.read_text(encoding='utf-8'))['text'] == 'Unsaved text.'

# New-file failure must not replace the current editor or its file identity.
with patch('writing.atomic_json', side_effect=OSError('new-file disk full')):
    assert not writer.newDraft('ja')
    assert writer.currentPath == str(essay)
    assert writer.current['text'] == 'Unsaved text.'

# A failed save prevents deletion, and a failed recycle keeps editor and disk.
with patch('writing.atomic_json', side_effect=OSError('save failure')):
    assert not writer.saveDraft('Regression', 'topic', 'Latest unsaved draft.')
    assert not writer.deleteDraft(str(essay))
    assert essay.exists() and writer.current['text'] == 'Latest unsaved draft.'
assert writer.retrySave()
with patch('core.storage.DataStore.trash_essay', side_effect=OSError('recycle denied')):
    assert not writer.deleteDraft(str(essay))
    assert essay.exists() and writer.currentPath == str(essay)
    assert writer.current['text'] == 'Latest unsaved draft.'

# Timer writes must pause with an actionable error instead of escaping a Qt slot.
writer._draft.update(task_id='fixture', task_prompt='topic', task_limit=60, task_elapsed=0, task_state='ready')
with patch('writing.atomic_json', side_effect=OSError('timer disk full')):
    writer.startTask()
    assert writer.saveError and not writer._clock.isActive()
    assert writer.current['task_state'] == 'paused'
assert writer.retrySave()

assert settings.dataSafety.backup()
snapshot = settings.dataSafety.snapshots[0]['name']
writer.deleteDraft(str(essay))
assert not essay.exists()
assert settings.dataSafety.essays
assert settings.dataSafety.restoreEssay(settings.dataSafety.essays[0]['id'])
assert essay.exists() and writer.drafts
assert settings.dataSafety.scheduleRestore(snapshot)
assert settings.dataSafety.restorePending
settings.dataSafety.cancelRestore()
assert not settings.dataSafety.restorePending

for width, height in [(900, 640), (1180, 820), (1600, 1000)]:
    window.setWidth(width); window.setHeight(height)
    app.processEvents()
    assert window.width() == width
    scroll = window.findChild(QObject, 'settingsFlick')
    scroll.setProperty('contentY', max(0, scroll.property('contentHeight') - scroll.property('height')))
    QTest.qWait(200)
    capture_folder = ROOT / 'release-verification/data-safety-closeout'
    capture_folder.mkdir(parents=True, exist_ok=True)
    assert window.grabWindow().save(str(capture_folder / f'settings-{width}x{height}.png'))
captures = ROOT / 'release-verification' / 'data-safety'
captures.mkdir(parents=True, exist_ok=True)
window.setWidth(1180); window.setHeight(820)
app.processEvents()
QTest.qWait(350)
window.grabWindow().save(str(captures / 'settings.png'))

# Directory lock prevents another instance using the same records.
first = QLockFile(str(DATA.with_name('data.lock')))
second = QLockFile(str(DATA.with_name('data.lock')))
assert first.tryLock(0) and not second.tryLock(0)
first.unlock()
assert second.tryLock(0)
second.unlock()

# Corrupt material collections cannot be silently replaced.
material_path = DATA / 'writing-materials.json'
material_path.write_text('{broken', encoding='utf-8')
other = WritingBridge()
assert other.saveMaterial('en', 'vocabulary', 'example', 'context', '') == ''
assert material_path.read_text(encoding='utf-8') == '{broken'
assert '失败' in other.status

# A well-formed JSON collection with invalid entries is also kept intact.
material_path.write_text('{"items":[null]}', encoding='utf-8')
other = WritingBridge()
assert other.saveMaterial('en', 'vocabulary', 'example', 'context', '') == ''
assert material_path.read_text(encoding='utf-8') == '{"items":[null]}'

# The new background manual action keeps the Qt event loop alive on a larger
# self-authored fixture; record duration and GUI heartbeat gap for review.
import time
for i in range(800):
    fixture = DATA / 'benchmark' / f'{i:04}.json'
    fixture.parent.mkdir(exist_ok=True)
    fixture.write_text(json.dumps({'text': 'Self-authored backup benchmark. ' * 120}), encoding='utf-8')
started = time.perf_counter()
last = started
max_gap = 0
settings.dataSafety.backupAsync()
while settings.dataSafety.busy and time.perf_counter() - started < 90:
    app.processEvents()
    now = time.perf_counter()
    max_gap = max(max_gap, now - last)
    last = now
    # qWait can hold the GIL in this synchronous harness; real app.exec releases
    # it. Sleep briefly between event pumps so the Python worker can run too.
    time.sleep(0.005)
assert not settings.dataSafety.busy and '已创建' in settings.dataSafety.status, settings.dataSafety.status
performance = {'backup_seconds': round(time.perf_counter() - started, 3),
               'max_event_loop_gap_seconds': round(max_gap, 3), 'fixture_files': 800}
assert max_gap < 0.5, performance
(capture_folder / 'performance.json').write_text(json.dumps(performance, indent=2), encoding='utf-8')

unexpected = [w for w in warnings if 'PlaceholderText: Binding loop' not in w]
assert not unexpected, unexpected
print('PASS: real QML, failed-save/retry/close, recycle, backup scheduling, lock, corrupt favorites, three sizes')
study.close()
window.close()
engine.deleteLater()
app.processEvents()
temporary.cleanup()
