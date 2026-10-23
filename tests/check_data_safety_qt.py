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

unexpected = [w for w in warnings if 'PlaceholderText: Binding loop' not in w]
assert not unexpected, unexpected
print('PASS: real QML, failed-save/retry/close, recycle, backup scheduling, lock, corrupt favorites, three sizes')
study.close()
window.close()
engine.deleteLater()
app.processEvents()
temporary.cleanup()
