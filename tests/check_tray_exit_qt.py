"""Verify the real tray QAction, including minimized/hidden windows and save veto."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'test-download/tray-exit-check'
OUT.mkdir(parents=True, exist_ok=True)

if '--child' not in sys.argv:
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        for mode in ('minimized', 'hidden', 'save-veto'):
            data = Path(temporary) / mode / 'data'
            start = time.perf_counter()
            for attempt in range(2 if mode != 'save-veto' else 1):
                # The second launch uses the same directory: the first must release its lock.
                run = subprocess.run([sys.executable, __file__, '--child', mode, str(data)],
                    cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15)
                assert run.returncode == 0, (mode, run.stdout, run.stderr)
                row = json.loads((OUT / f'{mode}.json').read_text(encoding='utf-8'))
                assert row['passed'], row
            results.append({'mode': mode, 'seconds': round(time.perf_counter()-start, 2), **row})
    (OUT/'result.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))
    raise SystemExit(0)

mode, directory = sys.argv[-2:]
os.environ['JUJIAN_DATA_DIR'] = directory
from PySide6.QtCore import QTimer, Qt
from PySide6.QtQml import QQmlEngine
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
import app as application

result = {'mode': mode, 'trigger_count': 0}
original = application.use_windows_window_effects

def inspect(window):
    original(window)
    context = QQmlEngine.contextForObject(window)
    actions = context.contextProperty('windowActions')
    settings = context.contextProperty('settings')
    writer = context.contextProperty('writer')
    assert settings.saveCloseBehavior('tray')
    assert writer.newDraft('ja')
    assert writer.saveDraft('Tray check', '', '保存した本文。')
    app = QApplication.instance()
    app.aboutToQuit.connect(lambda: result.update(about_to_quit=True))

    def prepare():
        if mode == 'hidden':
            assert not window.close()  # Normal close still hides to tray.
            assert not window.isVisible()
        else:
            actions.minimize()
        if mode == 'save-veto':
            writer._save_error = 'Injected save failure for tray verification'

    def trigger():
        result['before_exit_visible'] = window.isVisible()
        result['before_exit_minimized'] = window.windowState() == Qt.WindowMinimized
        tray = app.findChild(QSystemTrayIcon)
        assert tray is not None
        result['trigger_count'] += 1
        tray.contextMenu().actions()[-1].trigger()
        if mode == 'save-veto':
            QTimer.singleShot(250, verify_veto)

    def verify_veto():
        result['save_veto_restored_window'] = window.isVisible() and window.windowState() != Qt.WindowMinimized
        result['save_veto_kept_event_loop'] = not result.get('about_to_quit', False)
        result['save_veto_kept_draft'] = writer.saveError != ''
        writer._save_error = ''
        actions.exit()

    def watchdog():
        result['watchdog'] = True
        app.quit()

    QTimer.singleShot(250, prepare)
    QTimer.singleShot(600, trigger)
    QTimer.singleShot(5000, watchdog)

application.use_windows_window_effects = inspect
result['exit_code'] = application.main()
drafts = list((Path(directory)/'essays').glob('*.json'))
result['draft_preserved'] = any(json.loads(path.read_text(encoding='utf-8')).get('text') == '保存した本文。' for path in drafts)
result['passed'] = result.get('about_to_quit', False) and not result.get('watchdog') and result['draft_preserved']
if mode == 'save-veto':
    result['passed'] = result['passed'] and all(result.get(name) for name in (
        'save_veto_restored_window', 'save_veto_kept_event_loop', 'save_veto_kept_draft'))
(OUT/f'{mode}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
raise SystemExit(0 if result['passed'] else 1)
