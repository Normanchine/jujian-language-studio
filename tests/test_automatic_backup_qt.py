"""Daily backup must leave the first window responsive while it runs."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from data_safety import DataSafetyBridge


class AutomaticBackupTests(unittest.TestCase):
    def test_automatic_backup_does_not_block_qt_event_loop(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as folder:
            bridge = DataSafetyBridge(Path(folder) / 'data')
            original = bridge.store.daily_snapshot

            def slow_snapshot():
                time.sleep(0.25)
                original()

            with patch.object(bridge.store, 'daily_snapshot', side_effect=slow_snapshot):
                start = time.perf_counter()
                bridge.automaticBackup()
                self.assertLess(time.perf_counter() - start, 0.1)
                deadline = time.perf_counter() + 3
                while bridge._automatic_running and time.perf_counter() < deadline:
                    app.processEvents()
                    time.sleep(0.01)
                app.processEvents()
                self.assertFalse(bridge._automatic_running)
                self.assertIn('当日备份已就绪', bridge.status)
                self.assertEqual(1, len(list(bridge.store.backups.glob('*-daily.zip'))))


if __name__ == '__main__':
    unittest.main()
