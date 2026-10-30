"""Multi-passage file loading and article-selector behavior in real QML."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
temporary = tempfile.TemporaryDirectory(prefix='jujian-multipaper-ui-')
os.environ['JUJIAN_DATA_DIR'] = str(Path(temporary.name) / 'data')
os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import QObject, QUrl, QMetaObject
from PySide6.QtTest import QTest
from preview_writing import create_preview
from multipaper_fixture import PAPERS

app, engine, bridges, window = create_preview(Path(temporary.name) / 'data', reading_bank=False)
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(row.toString() for row in rows))
reader = bridges['reading']
window.setProperty('page', 'reading')
dialog = window.findChild(QObject, 'readingPaperImportDialog')
QMetaObject.invokeMethod(dialog, 'open')
file = next((ROOT / 'test-download/multipaper-20261030/converted-docx').rglob('*.md'))
reader.paperImporter.loadFile(QUrl.fromLocalFile(str(file)).toString(), 'local', '', '', 'en')
deadline = time.monotonic() + 10
while reader.paperImporter.view['busy'] and time.monotonic() < deadline:
    app.processEvents(); time.sleep(.01)
app.processEvents()
assert reader.paperImporter.view['parsed'] and reader.paperImporter.view['questionCount'] == 6
selector = window.findChild(QObject, 'readingPaperSelector')
assert selector.property('count') == 3
assert not dialog.property('revealAnswers') and dialog.property('protectSource')
for i, expected in enumerate(PAPERS):
    selector.setProperty('currentIndex', i)
    QTest.qWait(100)
    assert expected['body'] == dialog.property('currentPaper')['body']
selector.setProperty('currentIndex', 1)
QTest.qWait(100)
reader.paperImporter.includeQuestion(1, 2, False)
QTest.qWait(100)
assert selector.property('currentIndex') == 1, 'Changing inclusion must not jump to another passage'
assert reader.paperImporter.view['selectedCount'] == 5
reader.paperImporter.includeQuestion(1, 2, True)
QTest.qWait(100)
assert selector.property('currentIndex') == 1
output = ROOT / 'release-verification/multipaper-20261030'
output.mkdir(parents=True, exist_ok=True)
assert window.grabWindow().save(str(output / 'three-passages-preview.png'))
assert not warnings, warnings
(output / 'qt-result.json').write_text(json.dumps({'passed': True, 'papers': 3, 'questions': 6,
    'selector_switching': True, 'selection_stays_after_edit': True, 'answers_hidden': True, 'qml_warnings': warnings}, indent=2), encoding='utf-8')
print('PASS: real file load, three passage selector, independent questions, no answer reveal, no selection jump')
reader.leave(); reader.paperImporter.close(); bridges['study'].close()
window.close(); engine.deleteLater(); app.processEvents(); app._preview_data_lock.unlock()
temporary.cleanup()
