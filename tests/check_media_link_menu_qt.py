"""Owned-window context-menu rendering and clipboard actions with restoration."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
temporary = tempfile.TemporaryDirectory(prefix='jujian-menu-ui-')
os.environ['JUJIAN_DATA_DIR'] = str(Path(temporary.name) / 'data')
os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import QObject, QMimeData, Qt, QPointF, QMetaObject
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
import shiboken6
from preview_writing import create_preview

app, engine, bridges, window = create_preview(Path(temporary.name) / 'data', reading_bank=False)
quick = shiboken6.wrapInstance(shiboken6.getCppPointer(window)[0], QQuickWindow)
window.setProperty('page', 'home')
warnings = []
engine.warnings.connect(lambda values: warnings.extend(v.toString() for v in values))
output = ROOT / 'release-verification/reading-paper-import'
output.mkdir(parents=True, exist_ok=True)
clipboard = app.clipboard()
mime = clipboard.mimeData()
saved = {format: bytes(mime.data(format)) for format in mime.formats()} if mime else {}


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


def click(name, button=Qt.LeftButton):
    item = find(name)
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
    QTest.mouseClick(quick, button, Qt.NoModifier, point)
    QTest.qWait(150)


try:
    field = find('mediaLinkField')
    QTest.qWait(250)
    clipboard.setText('https://example.com/self-authored-media')
    click('mediaLinkField', Qt.RightButton)
    menu = find('mediaLinkContextMenu')
    assert menu.property('visible'), 'Right click must open styled context menu'
    assert not find('textMenuCut').property('enabled')
    assert find('textMenuPaste').property('enabled')
    assert window.grabWindow().save(str(output / 'media-link-menu-empty.png'))
    click('textMenuPaste')
    assert field.property('text') == 'https://example.com/self-authored-media'
    assert not menu.property('visible')
    field.selectAll()
    before = field.property('selectedText')
    click('mediaLinkField', Qt.RightButton)
    assert field.property('selectedText') == before
    assert find('textMenuCopy').property('enabled') and find('textMenuCut').property('enabled')
    assert window.grabWindow().save(str(output / 'media-link-menu-selection.png'))
    click('textMenuCopy')
    assert clipboard.text() == before
    click('mediaLinkField', Qt.RightButton)
    click('textMenuCut')
    assert field.property('text') == ''
    click('mediaLinkField', Qt.RightButton)
    click('textMenuUndo')
    assert field.property('text') == before
    assert not warnings, warnings
    (output / 'media-menu-result.json').write_text(json.dumps({'passed': True, 'qml_warnings': warnings,
        'right_click': True, 'paste_copy_cut_undo': True, 'selection_preserved': True}), encoding='utf-8')
    print('PASS: styled right-click menu, disabled states, paste/copy/cut/undo, selection preserved, no QML warnings')
finally:
    restore = QMimeData()
    for format, data in saved.items():
        restore.setData(format, data)
    clipboard.setMimeData(restore)
    bridges['reading'].leave()
    bridges['study'].close()
    # The preview schedules its daily snapshot 1.5 seconds after startup.
    # Let that worker finish before removing the isolated temporary data tree.
    QTest.qWait(1600)
    for _ in range(100):
        if not bridges['settings'].dataSafety.busy:
            break
        time.sleep(0.1)
        app.processEvents()
    assert not bridges['settings'].dataSafety.busy
    window.close()
    engine.deleteLater()
    app.processEvents()
    app._preview_data_lock.unlock()
    temporary.cleanup()
