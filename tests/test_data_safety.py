"""Offline regression: python -m unittest discover -s tests -v."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from core.storage import DataStore, atomic_json


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


if __name__ == '__main__':
    unittest.main()
