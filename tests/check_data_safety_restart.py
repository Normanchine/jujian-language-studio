"""Two real app.main processes: arrange restore, exit, restart, inspect bridges.

The harness injects checks at the existing window-effects callback; application
startup, directory locking, restore and bridge construction remain unchanged.
No production test switches, credentials, network or personal data are used.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def records(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.suffix.lower() in {'.json', '.txt'}}


def child(phase, folder):
    data = folder / 'data'
    os.environ['JUJIAN_DATA_DIR'] = str(data)
    os.environ['JUJIAN_WRITING_DEMO'] = '1'
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    if phase == 'legacy-preview':
        from core.storage import DataStore
        expected = json.loads((folder / 'expected.json').read_text(encoding='utf-8'))
        store = DataStore(data)
        store.schedule_restore(expected['snapshot'])
        from preview_writing import create_preview
        preview_app, engine, bridges, window = create_preview(data, reading_bank=False)
        assert records(data) == expected['records']
        assert not store.pending.exists()
        writer = bridges['writer']
        writer.openDraft(expected['essay'])
        assert writer.current['text'] == 'Original text before backup.'
        result = {'phase': phase, 'pid': os.getpid(), 'passed': True,
                  'restored_before_bridges': True, 'isolated_paths': True}
        (folder / (phase + '.json')).write_text(json.dumps(result), encoding='utf-8')
        window.close()
        bridges['study'].close()
        engine.deleteLater()
        preview_app.processEvents()
        return
    import app as application
    from PySide6.QtCore import QTimer
    from PySide6.QtQml import QQmlEngine
    from PySide6.QtWidgets import QApplication
    from core.storage import atomic_json, DataStore

    result = {'phase': phase, 'pid': os.getpid()}
    original = application.use_windows_window_effects

    def inspect_window(window):
        original(window)
        def inspect():
            try:
                context = QQmlEngine.contextForObject(window)
                writer = context.contextProperty('writer')
                safety = context.contextProperty('settings').dataSafety
                store = DataStore(data)
                if phase == 'arrange':
                    assert writer.newDraft('en')
                    assert writer.saveDraft('Restart fixture', 'Self-authored test', 'Original text before backup.')
                    essay = writer.currentPath
                    assert writer.saveWritingNote('', 'Original note', 'Original text', essay, 'en')
                    writer.toggleDraftFavorite(essay)
                    atomic_json(data / 'reading-home.json', {'schema': 1, 'fixtureProgress': {'paragraph': 7}})
                    (data / 'fixture.wav').write_bytes(b'isolated-media-fixture')
                    assert safety.backup()
                    snapshot = safety.snapshots[0]['name']
                    expected = records(data)
                    (folder / 'expected.json').write_text(json.dumps({'records': expected, 'essay': essay, 'snapshot': snapshot}), encoding='utf-8')
                    assert writer.saveDraft('Changed after backup', 'Self-authored test', 'Newer record retained in before-restore backup.')
                    assert safety.scheduleRestore(snapshot)
                    safety.cancelRestore()
                    assert not safety.restorePending
                    assert safety.scheduleRestore(snapshot)
                    assert safety.restorePending
                    # The same data directory is locked for the actual app lifetime.
                    lock_probe = subprocess.run([sys.executable, '-c',
                        'from core.session import open_data_session; import sys; '
                        'open_data_session(sys.argv[1])', str(data)], cwd=ROOT, capture_output=True, timeout=10)
                    assert lock_probe.returncode != 0 and b'OSError' in lock_probe.stderr
                    result['second_instance_rejected'] = True
                else:
                    expected = json.loads((folder / 'expected.json').read_text(encoding='utf-8'))
                    assert records(data) == expected['records'], 'restored JSON/TXT hashes differ'
                    assert not safety.restorePending and not store.journal.exists()
                    writer.openDraft(expected['essay'])
                    assert writer.current['text'] == 'Original text before backup.'
                    assert writer.current['favorite'] is True
                    assert any(n['text'] == 'Original note' for n in writer.notes)
                    assert json.loads((data / 'reading-home.json').read_text())['fixtureProgress']['paragraph'] == 7
                    assert (data / 'fixture.wav').read_bytes() == b'isolated-media-fixture'
                    before = next(store.backups.glob('*-before-restore.zip'))
                    from zipfile import ZipFile
                    with ZipFile(before) as archive:
                        relative = Path(expected['essay']).relative_to(data).as_posix()
                        assert json.loads(archive.read('data/' + relative))['text'].startswith('Newer record')
                    result.update(records_restored=len(expected['records']), media_preserved=True,
                                  newer_records_retained=True, bridge_loaded_restored_essay=True)
                result['passed'] = True
                window.close()
            except Exception:
                result['passed'] = False
                result['error'] = traceback.format_exc()
                QApplication.instance().exit(2)
            finally:
                (folder / (phase + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
        # Before startup automatic backup and without bypassing normal app setup.
        QTimer.singleShot(100, inspect)
    application.use_windows_window_effects = inspect_window
    raise SystemExit(application.main())


def main():
    output = ROOT / 'release-verification/data-safety-closeout'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jujian-restart-') as temporary:
        folder = Path(temporary)
        results = []
        for phase in ('arrange', 'restore', 'legacy-preview'):
            run = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child', phase, str(folder)],
                                 cwd=ROOT, capture_output=True, timeout=40)
            report = folder / (phase + '.json')
            row = json.loads(report.read_text()) if report.exists() else {'passed': False}
            row['exit_code'] = run.returncode
            results.append(row)
            if run.returncode or not row.get('passed'):
                print(run.stdout.decode(errors='replace'), run.stderr.decode(errors='replace'))
                print(row)
                break
        passed = len(results) == 3 and all(r.get('passed') and r['exit_code'] == 0 for r in results)
        (output / 'restart.json').write_text(json.dumps({'passed': passed, 'processes': results}, indent=2), encoding='utf-8')
        assert passed, results
        print('PASS: two real app processes, directory lock, cancel, restore, essay/note/favorite/progress hashes, media, before-restore backup')


if __name__ == '__main__':
    if '--child' in sys.argv:
        child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
