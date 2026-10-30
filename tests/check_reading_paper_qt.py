"""Real QML import->answer->submit interaction, independent self-authored data."""
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['QT_QPA_PLATFORM'] = 'windows'
temporary = tempfile.TemporaryDirectory(prefix='jujian-paper-ui-')
os.environ['JUJIAN_DATA_DIR'] = str(Path(temporary.name) / 'data')

from PySide6.QtCore import QObject, QPoint, QMetaObject, QUrl
from PySide6.QtQml import QQmlExpression, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from PySide6.QtQuick import QQuickWindow
import shiboken6
from preview_writing import create_preview

sample = runpy.run_path(str(ROOT / 'tests/test_reading_paper_import.py'))['SAMPLE']
app, engine, bridges, window = create_preview(Path(temporary.name) / 'data', reading_bank=False)
warnings = []
engine.warnings.connect(lambda values: warnings.extend(v.toString() for v in values))
output = ROOT / 'release-verification/reading-paper-import'
output.mkdir(parents=True, exist_ok=True)
quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)


def find(name):
    pending = [quick.contentItem()]
    while pending:
        item = pending.pop()
        if item.objectName() == name and item.isVisible():
            return item
        pending.extend(item.childItems())
    item = window.findChild(QObject, name)
    assert item is not None, name
    return item


def expression(item, code):
    value = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    value.evaluate()
    assert not value.hasError(), value.error().toString()


def click(name):
    item = find(name)
    point = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
    QTest.qWait(120)


window.setProperty('page', 'reading')
home = find('readingHome')
expression(home, 'openDestination("library")')
QTest.qWait(250)
click('readingImportPaper')
dialog = find('readingPaperImportDialog')
assert dialog.property('visible')
find('readingPaperImportTitle').setProperty('text', 'Community gardens · 自编导入演示')
find('readingPaperImportSource').setProperty('text', sample)
QTest.qWait(200)
assert dialog.property('protectSource') and not find('readingPaperImportSource').isVisible()
assert window.grabWindow().save(str(output / 'source-1180.png'))
click('readingPaperImportParse')
assert bridges['reading'].paperImporter.view['parsed']
assert bridges['reading'].paperImporter.view['missing'] == 1
assert not find('readingPaperImportSource').property('visible') or dialog.property('protectSource')
assert not dialog.property('revealAnswers'), 'Import preview must not reveal answer letters'
pending = [quick.contentItem()]
while pending:
    item = pending.pop()
    if item.objectName().startswith('readingPaperAnswer_'):
        assert not item.isVisible(), item.objectName()
    pending.extend(item.childItems())
assert not find('readingPaperImportSave').property('enabled')
QTest.qWait(150)
assert window.grabWindow().save(str(output / 'preview-1180.png'))
# Use the bridge for a scrolled-off answer; both binding and button state update.
bridges['reading'].paperImporter.setAnswer(0, 1, 'C')
QTest.qWait(150)
click('readingPaperImportConfirm')
assert find('readingPaperImportSave').property('enabled')
window.resize(900, 640)
QTest.qWait(200)
assert dialog.property('width') <= 900
assert window.grabWindow().save(str(output / 'preview-900.png'))
window.resize(1600, 1000)
QTest.qWait(200)
assert window.grabWindow().save(str(output / 'preview-1600.png'))
window.resize(1180, 820)
QTest.qWait(150)
click('readingPaperImportSave')
reader = bridges['reading']
assert reader.view['stage'] == 'exercise', reader.view
assert not dialog.property('visible')
click('readingOption_B')
click('readingPracticeNext')
click('readingOption_C')
click('readingPracticeSubmit')
click('readingConfirmSubmit')
assert reader.view['stage'] == 'review' and reader.view['correct'] == 2, reader.view
QTest.qWait(150)
assert window.grabWindow().save(str(output / 'review-1180.png'))
assert not warnings, warnings
(output / 'qt-result.json').write_text(json.dumps({'passed': True, 'qml_warnings': warnings,
    'imported_papers': len(reader.paperImporter.stored_papers()), 'correct': reader.view['correct']}, indent=2), encoding='utf-8')
print('PASS: real QML import/confirmation, three sizes, practice, submit/review 2/2, no QML warnings')
reader.leave()
bridges['study'].close()
window.close()
engine.deleteLater()
app.processEvents()
app._preview_data_lock.unlock()
temporary.cleanup()
