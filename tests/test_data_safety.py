"""Offline regression: python -m unittest discover -s tests -v."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from core.storage import DataStore, atomic_json, atomic_text


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'data'
        self.root.mkdir()
        self.store = DataStore(self.root)

    def test_compact_checkpoint_preserves_content_and_write_protection(self):
        path = self.root / 'project.json'
        value = {'schema_version': 1, 'title': '长视频', 'segments': [{'text': '字幕', 'start': 0}], 'playback_ms': 5000}
        atomic_json(path, value)
        formatted_size = path.stat().st_size
        atomic_json(path, value, compact=True)
        self.assertEqual(value, json.loads(path.read_text(encoding='utf-8')))
        self.assertLess(path.stat().st_size, formatted_size)
        before = path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('locked')):
            with self.assertRaises(OSError):
                atomic_json(path, {**value, 'playback_ms': 10000}, compact=True)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(self.root.glob('*.tmp')))
        for content in ('broken', '{"schema_version":99}', '[]'):
            path.write_text(content, encoding='utf-8')
            with self.assertRaises(OSError):
                atomic_json(path, value, compact=True)
            self.assertEqual(content, path.read_text(encoding='utf-8'))

    def test_failed_replace_preserves_original_and_removes_temporary(self):
        path = self.root / 'essay.json'
        atomic_json(path, {'text': 'original'})
        before = path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('locked')):
            with self.assertRaises(OSError):
                atomic_json(path, {'text': 'changed'})
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(self.root.glob('*.tmp')))

    def test_corruption_and_future_schema_are_not_overwritten(self):
        path = self.root / 'favorites.json'
        for content in ['broken', '[]', '{"items":null}', '{"items":[],"schema_version":99}']:
            path.write_text(content, encoding='utf-8')
            with self.assertRaises(OSError):
                atomic_json(path, {'schema_version': 2, 'items': []})
            self.assertEqual(content, path.read_text(encoding='utf-8'))

    def test_list_records_can_be_updated_without_allowing_type_changes(self):
        path = self.root / 'reading/intensive/english/lookups/manual.json'
        atomic_json(path, [{'id': 'first', 'meaning': '年'}])
        atomic_json(path, [{'id': 'first', 'meaning': '年'}, {'id': 'second', 'meaning': '十亿'}])
        self.assertEqual(2, len(json.loads(path.read_text(encoding='utf-8'))))
        atomic_json(path, [])
        self.assertEqual([], json.loads(path.read_text(encoding='utf-8')))
        with self.assertRaises(OSError):
            atomic_json(path, {'items': []})
        self.assertEqual([], json.loads(path.read_text(encoding='utf-8')))

    def test_restore_exact_records_keeps_media_and_backs_up_latest(self):
        atomic_json(self.root / 'essays/a.json', {'text': 'before', 'schema_version': 1})
        (self.root / 'sound.wav').write_bytes(b'media')
        snapshot = self.store.snapshot()
        atomic_json(self.root / 'essays/a.json', {'text': 'after', 'schema_version': 1})
        atomic_json(self.root / 'new.json', {'new': True})
        self.store.schedule_restore(snapshot.name)
        self.assertTrue(self.store.apply_pending())
        self.assertEqual('before', json.loads((self.root / 'essays/a.json').read_text())['text'])
        self.assertFalse((self.root / 'new.json').exists())
        self.assertEqual(b'media', (self.root / 'sound.wav').read_bytes())
        saved = next(self.store.backups.glob('*-before-restore.zip'))
        with ZipFile(saved) as archive:
            self.assertEqual('after', json.loads(archive.read('data/essays/a.json'))['text'])

    def test_tampered_backup_and_wrong_directory_rejected(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        path = self.store.snapshot()
        with ZipFile(path, 'a') as archive:
            archive.writestr('data/extra.json', '{}')
        with self.assertRaises(OSError):
            self.store.schedule_restore(path.name)
        with self.assertRaises(OSError):
            self.store.schedule_restore('../foreign.zip')

    def test_pending_checksum_and_interrupted_swap(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        path = self.store.snapshot()
        self.store.schedule_restore(path.name)
        path.write_bytes(b'changed')
        with self.assertRaises(OSError):
            self.store.apply_pending()
        old = self.root.with_name('data-before-restore-test')
        atomic_json(self.store.journal, {'old': str(old)})
        self.root.rename(old)
        self.store.recover_interrupted()
        self.assertTrue((self.root / 'a.json').exists())

    def test_recycle_restore_conflict_and_original_bytes(self):
        path = self.root / 'essays/a.json'
        atomic_json(path, {'title': 'my essay', 'text': 'original'})
        before = path.read_bytes()
        key = self.store.trash_essay(path)
        self.assertFalse(path.exists())
        atomic_json(path, {'text': 'new'})
        with self.assertRaises(OSError):
            self.store.restore_essay(key)
        path.unlink()
        self.store.restore_essay(key)
        self.assertEqual(before, path.read_bytes())

    def test_daily_is_idempotent(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        self.store.daily_snapshot()
        self.store.daily_snapshot()
        self.assertEqual(1, len(list(self.store.backups.glob('*-daily.zip'))))
        self.assertEqual(1, len(list(self.store.backups.glob('*-weekly-*.zip'))))

    def test_disk_full_before_replace_preserves_original(self):
        path = self.root / 'a.json'
        atomic_json(path, {'value': 'original'})
        before = path.read_bytes()
        with patch('core.storage.os.fsync', side_effect=OSError(28, 'disk full')):
            with self.assertRaises(OSError):
                atomic_json(path, {'value': 'new'})
        self.assertEqual(before, path.read_bytes())
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_semantically_corrupt_collections_are_preserved(self):
        path = self.root / 'favorites.json'
        for value in ({'items': [None]}, {'items': ['broken']}):
            path.write_text(json.dumps(value), encoding='utf-8')
            before = path.read_bytes()
            with self.assertRaises(OSError):
                atomic_json(path, {'items': []})
            self.assertEqual(before, path.read_bytes())

    def test_corrupt_journal_stops_without_changing_records(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        for value in ('{broken', '[]', '{"old":"C:/elsewhere"}'):
            self.store.backups.mkdir(exist_ok=True)
            self.store.journal.write_text(value, encoding='utf-8')
            with self.assertRaises(OSError):
                self.store.apply_pending()
            self.assertEqual({'a': 1}, json.loads((self.root / 'a.json').read_text()))
            self.assertTrue(self.store.journal.exists())

    def test_swap_failure_rolls_back_and_retains_pending(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        snapshot = self.store.snapshot()
        atomic_json(self.root / 'a.json', {'a': 2})
        self.store.schedule_restore(snapshot.name)
        original = Path.rename
        def fail_stage(path, target):
            if path.name.startswith('data-restore-'):
                raise OSError('simulated rename failure')
            return original(path, target)
        with patch.object(Path, 'rename', fail_stage):
            with self.assertRaises(OSError):
                self.store.apply_pending()
        self.assertEqual({'a': 2}, json.loads((self.root / 'a.json').read_text()))
        self.assertTrue(self.store.pending.exists())
        self.assertTrue(self.store.apply_pending())
        self.assertEqual({'a': 1}, json.loads((self.root / 'a.json').read_text()))

    def test_committed_restore_cleanup_does_not_roll_back(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        old = self.root.with_name('data-before-restore-committed')
        old.mkdir()
        atomic_json(old / 'a.json', {'a': 2})
        atomic_json(self.store.journal, {'old': str(old), 'committed': True})
        self.store.recover_interrupted()
        self.assertEqual({'a': 1}, json.loads((self.root / 'a.json').read_text()))
        self.assertTrue(old.exists())

    def test_invalid_manifest_paths_and_fields_rejected(self):
        for relative, info in [('CON.json', {}), ('a.json.', {}), ('a.json', {'size': -1}),
                               ('a.json', {'size': 0, 'sha256': 1})]:
            path = self.store.backups / 'invalid.zip'
            path.parent.mkdir(exist_ok=True)
            with ZipFile(path, 'w') as archive:
                archive.writestr('manifest.json', json.dumps({'format': 1, 'source': str(self.root), 'files': {relative: info}}))
            with self.assertRaises(OSError):
                self.store.verify(path)

    def test_automatic_rotation_preserves_manual_and_recovery(self):
        self.store.backups.mkdir()
        for i in range(20):
            for kind in ('daily', 'weekly-2026-W01'):
                (self.store.backups / f'20000101-000000-{i:06}-{kind}.zip').touch()
        manual = self.store.snapshot('manual')
        recovery = self.store.snapshot('before-restore')
        self.store.daily_snapshot()
        self.assertEqual(14, len(list(self.store.backups.glob('*-daily.zip'))))
        self.assertEqual(8, len(list(self.store.backups.glob('*-weekly-*.zip'))))
        self.assertTrue(manual.exists() and recovery.exists())

    def test_snapshot_detects_uncoordinated_writer(self):
        atomic_json(self.root / 'a.json', {'a': 1})
        verify = self.store.verify
        def change_after_read(path):
            result = verify(path)
            (self.root / 'a.json').write_text('{"a":2}', encoding='utf-8')
            return result
        with patch.object(self.store, 'verify', side_effect=change_after_read):
            with self.assertRaises(OSError):
                self.store.snapshot()
        self.assertEqual([], list(self.store.backups.glob('*.zip')))

    def test_text_pointer_replace_failure_preserves_old_pointer(self):
        path = self.root / 'last-project.txt'
        atomic_text(path, 'old-project')
        with patch.object(Path, 'replace', side_effect=OSError('locked')):
            with self.assertRaises(OSError):
                atomic_text(path, 'new-project')
        self.assertEqual('old-project', path.read_text())
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_concurrent_saves_and_snapshots_keep_complete_records(self):
        from concurrent.futures import ThreadPoolExecutor
        atomic_json(self.root / 'a.json', {'revision': 0, 'text': 'fixture' * 100})
        def work(number):
            if number % 3:
                atomic_json(self.root / 'a.json', {'revision': number, 'text': 'fixture' * 100})
            else:
                self.store.verify(self.store.snapshot())
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(work, range(24)))
        self.assertEqual('fixture' * 100, json.loads((self.root / 'a.json').read_text())['text'])
        self.assertFalse(list(self.root.glob('*.tmp')))

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows junction regression')
    def test_junction_is_rejected_before_backup_or_restore(self):
        import subprocess
        import os
        outside = self.root.parent / 'outside'
        outside.mkdir()
        atomic_json(outside / 'record.json', {'private': 'fixture'})
        junction = self.root / 'linked'
        # Windows junctions require no developer-mode symlink privilege.
        environment = {**os.environ, 'JUJIAN_TEST_LINK': str(junction), 'JUJIAN_TEST_TARGET': str(outside)}
        run = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                              '$ErrorActionPreference="Stop"; New-Item -ItemType Junction -Path $env:JUJIAN_TEST_LINK -Target $env:JUJIAN_TEST_TARGET | Out-Null'],
                             env=environment, capture_output=True)
        if run.returncode:
            self.fail(run.stderr.decode(errors='replace'))
        with self.assertRaises(OSError):
            self.store.snapshot()
        self.assertEqual({'private': 'fixture'}, json.loads((outside / 'record.json').read_text()))


if __name__ == '__main__':
    unittest.main()
