"""Persistent independent import preview with a clearly self-authored example."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'test-download/reading-paper-preview'
os.environ['JUJIAN_DATA_DIR'] = str(FOLDER / 'data')
from PySide6.QtCore import QObject, QTimer
from PySide6.QtQml import QQmlExpression, QQmlEngine
from preview_writing import create_preview


def create_import_preview():
    settings_path = FOLDER / 'data/settings.json'
    if not settings_path.exists():
        try:
            source_settings = json.loads((ROOT / 'data/settings.json').read_text(encoding='utf-8'))
            if not isinstance(source_settings, dict):
                raise ValueError('Invalid source settings')
            public_fields = {key: source_settings[key] for key in ('cloud_endpoint', 'cloud_model')
                             if isinstance(source_settings.get(key), str)}
            if public_fields:
                from core.storage import atomic_json
                atomic_json(settings_path, public_fields)
        except (OSError, ValueError, TypeError):
            pass
    app, engine, bridges, window = create_preview(FOLDER / 'data', animations=False, reading_bank=False)
    window.setProperty('page', 'reading')
    window.setProperty('title', '句间 · 阅读题导入预览（独立数据）')
    window.resize(1320, 900)
    def show():
        home = window.findChild(QObject, 'readingHome')
        context = QQmlEngine.contextForObject(home)
        action = QQmlExpression(context, home, 'openDestination("library")')
        action.evaluate()
        dialog = window.findChild(QObject, 'readingPaperImportDialog')
        current = bridges['reading'].paperImporter.view
        text = current['raw'] or (ROOT / 'assets/reading-import-demo.md').read_text(encoding='utf-8')
        title = current['title'] or 'Community gardens · 自编示例'
        name = current['filename'] or 'reading-import-demo.md'
        expression = QQmlExpression(QQmlEngine.contextForObject(dialog), dialog,
            'open();populate(' + ','.join(json.dumps(v, ensure_ascii=False) for v in (text, title, name)) + ');parse()')
        expression.evaluate()
        if expression.hasError():
            raise RuntimeError(expression.error().toString())
        window.showNormal(); window.raise_(); window.requestActivate()
        def ready():
            FOLDER.mkdir(parents=True, exist_ok=True)
            window.grabWindow().save(str(FOLDER / 'visible-preview.png'))
            (FOLDER / 'ready.json').write_text(json.dumps({'pid': os.getpid(), 'isolated': True,
                'directory': str(FOLDER / 'data'), 'title': window.property('title')}, ensure_ascii=False, indent=2), encoding='utf-8')
        QTimer.singleShot(500, ready)
    QTimer.singleShot(300, show)
    return app, engine, bridges, window


if __name__ == '__main__':
    app, engine, bridges, window = create_import_preview()
    raise SystemExit(app.exec())
