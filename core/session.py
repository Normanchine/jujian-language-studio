"""Shared startup contract for the application and isolated source previews."""
from pathlib import Path


def open_data_session(root):
    from PySide6.QtCore import QLockFile
    from core.storage import DataStore
    root = Path(root).resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root.with_name(root.name + '.lock')))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise OSError('此数据目录已由另一个句间进程使用：' + str(root))
    try:
        DataStore(root).apply_pending()
    except Exception:
        lock.unlock()
        raise
    return lock
