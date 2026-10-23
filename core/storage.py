"""Fail-closed JSON writes and verifiable, offline data snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

LOCK = threading.RLock()


def atomic_json(path: Path, value: dict | list, *, compact: bool = False) -> None:
    path = Path(path)
    if not isinstance(value, (dict, list)):
        raise TypeError('JSON record must be an object or list')
    with LOCK:
        # Missing files are new records. Invalid existing records are never
        # silently replaced by a default/empty in-memory representation.
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding='utf-8'))
                if type(old) is not type(value):
                    raise ValueError('record type changed')
                if isinstance(value, dict):
                    if isinstance(value.get('items'), list) and not isinstance(old.get('items'), list):
                        raise ValueError('invalid items')
                    for key in ('schema_version', 'version', 'schema'):
                        if type(old.get(key)) is int and type(value.get(key)) is int and old[key] > value[key]:
                            raise ValueError('future data version')
            except (ValueError, UnicodeError) as exc:
                raise OSError(f'原文件损坏，已阻止覆盖：{path.name}；请从备份恢复') from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                if compact:
                    # Playback checkpoints run on the UI thread. The C encoder
                    # plus one write avoids thousands of small formatted writes.
                    stream.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
                else:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class DataStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.backups = self.root.with_name(self.root.name + '-backups')
        self.pending = self.backups / 'pending-restore.json'
        self.journal = self.backups / 'restore-journal.json'

    def snapshot(self, kind='manual') -> Path:
        with LOCK:
            self.backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            target = self.backups / f'{stamp}-{kind}.zip'
            temporary = target.with_suffix('.tmp')
            manifest = {'format': 1, 'created': datetime.now().isoformat(timespec='seconds'),
                        'kind': kind, 'source': str(self.root), 'files': {}}
            from core.paths import ASSETS
            match = re.search(r'appVersion:\s*"([^"]+)"', (ASSETS / 'qml/Main.qml').read_text(encoding='utf-8'))
            manifest['application_version'] = match.group(1) if match else 'unknown'
            try:
                with ZipFile(temporary, 'x', ZIP_DEFLATED) as archive:
                    for path in sorted(self.root.rglob('*')):
                        if path.is_symlink():
                            raise OSError('备份不跟随链接：' + str(path))
                        if not path.is_file() or path.suffix.lower() not in {'.json', '.txt'}:
                            continue
                        relative = path.relative_to(self.root).as_posix()
                        content = path.read_bytes()
                        manifest['files'][relative] = {'sha256': digest(content), 'size': len(content)}
                        archive.writestr('data/' + relative, content)
                    archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
                self.verify(temporary)
                # Detect writers which have not yet adopted the shared lock.
                for relative, info in manifest['files'].items():
                    if digest((self.root / relative).read_bytes()) != info['sha256']:
                        raise OSError('数据正在变化，请稍后备份')
                current = {p.relative_to(self.root).as_posix() for p in self.root.rglob('*')
                           if p.is_file() and p.suffix.lower() in {'.json', '.txt'}}
                if current != set(manifest['files']):
                    raise OSError('数据文件列表正在变化，请稍后备份')
                temporary.replace(target)
                return target
            finally:
                temporary.unlink(missing_ok=True)

    def verify(self, archive_path: Path) -> dict:
        try:
            with ZipFile(archive_path) as archive:
                if archive.getinfo('manifest.json').file_size > 4 * 1024 * 1024:
                    raise ValueError('备份清单过大')
                manifest = json.loads(archive.read('manifest.json'))
                if manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict):
                    raise ValueError('不支持的备份格式')
                names = archive.namelist()
                expected = {'manifest.json'}
                total = 0
                for relative, info in manifest['files'].items():
                    part = PurePosixPath(relative)
                    if (not relative or part.is_absolute() or '..' in part.parts or '\\' in relative
                            or ':' in relative or str(part) != relative):
                        raise ValueError('备份包含非法路径')
                    name = 'data/' + relative
                    expected.add(name)
                    member = archive.getinfo(name)
                    total += member.file_size
                    if total > 512 * 1024 * 1024 or member.file_size != info['size']:
                        raise ValueError('备份大小不符合清单或超过 512 MB')
                    content = archive.read(name)
                    if digest(content) != info['sha256']:
                        raise ValueError('备份校验失败：' + relative)
                if len(names) != len(set(names)) or set(names) != expected:
                    raise ValueError('备份文件列表不一致')
                return manifest
        except (KeyError, TypeError, ValueError) as exc:
            raise OSError('备份无效：' + str(exc)) from exc

    def schedule_restore(self, name: str):
        path = self.backups / name
        if path.parent != self.backups or path.suffix != '.zip':
            raise OSError('备份路径无效')
        manifest = self.verify(path)
        if Path(manifest['source']).resolve() != self.root:
            raise OSError('此备份属于另一个数据目录')
        atomic_json(self.pending, {'name': name, 'sha256': digest(path.read_bytes())})

    def recover_interrupted(self):
        """Roll back an interrupted directory swap before loading any bridges."""
        if not self.journal.exists():
            return
        state = json.loads(self.journal.read_text(encoding='utf-8'))
        old = Path(state['old'])
        if old.parent != self.root.parent or not old.name.startswith(self.root.name + '-before-restore-'):
            raise OSError('恢复日志路径无效')
        if old.exists():
            if self.root.exists():
                self.root.rename(self.root.with_name(self.root.name + '-interrupted-' + uuid4().hex))
            old.rename(self.root)
        self.journal.unlink()

    def apply_pending(self) -> bool:
        with LOCK:
            self.recover_interrupted()
            if not self.pending.exists():
                return False
            request = json.loads(self.pending.read_text(encoding='utf-8'))
            name = request['name']
            path = self.backups / name
            if path.parent != self.backups or digest(path.read_bytes()) != request['sha256']:
                raise OSError('待恢复备份已变化')
            manifest = self.verify(path)
            if Path(manifest['source']).resolve() != self.root:
                raise OSError('备份目录不匹配')
            self.snapshot('before-restore')
            stage = self.root.with_name(self.root.name + '-restore-' + uuid4().hex)
            old = self.root.with_name(self.root.name + '-before-restore-' + uuid4().hex)
            # Retain media/cache files. Restore the backed-up JSON/TXT domain exactly.
            shutil.copytree(self.root, stage)
            for item in stage.rglob('*'):
                if item.is_file() and item.suffix.lower() in {'.json', '.txt'}:
                    item.unlink()
            with ZipFile(path) as archive:
                for relative in manifest['files']:
                    output = stage / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(archive.read('data/' + relative))
            atomic_json(self.journal, {'old': str(old)})
            try:
                self.root.rename(old)
                stage.rename(self.root)
            except OSError:
                self.recover_interrupted()
                raise
            self.pending.unlink()
            self.journal.unlink()
            # Keep old directory as a second recovery option, never auto-delete it.
            return True

    def trash_essay(self, source: Path) -> str:
        with LOCK:
            source = Path(source).resolve()
            if source.parent != self.root / 'essays' or source.suffix != '.json':
                raise OSError('作文路径无效')
            entry = self.root / 'trash' / 'essays' / uuid4().hex
            entry.mkdir(parents=True)
            atomic_json(entry / 'entry.json', {'filename': source.name, 'deleted': datetime.now().isoformat(timespec='seconds')})
            source.rename(entry / 'content.json')
            return entry.name

    def restore_essay(self, entry_id: str):
        with LOCK:
            if not entry_id or any(c not in '0123456789abcdef' for c in entry_id):
                raise OSError('回收站条目无效')
            entry = self.root / 'trash' / 'essays' / entry_id
            metadata = json.loads((entry / 'entry.json').read_text(encoding='utf-8'))
            filename = metadata['filename']
            if Path(filename).name != filename or not filename.endswith('.json'):
                raise OSError('作文文件名无效')
            target = self.root / 'essays' / filename
            if target.exists():
                raise OSError('同名作文已存在，未覆盖')
            target.parent.mkdir(parents=True, exist_ok=True)
            (entry / 'content.json').rename(target)
            (entry / 'entry.json').unlink()
            entry.rmdir()

    def daily_snapshot(self):
        today = datetime.now().strftime('%Y%m%d')
        if not list(self.backups.glob(today + '-*-daily.zip')):
            self.snapshot('daily')
        # Only rotate automatic daily snapshots. Manual/recovery backups are retained.
        for old in sorted(self.backups.glob('*-daily.zip'), reverse=True)[14:]:
            old.unlink()
        week = datetime.now().strftime('%G-W%V')
        if not list(self.backups.glob('*-weekly-' + week + '.zip')):
            self.snapshot('weekly-' + week)
        for old in sorted(self.backups.glob('*-weekly-*.zip'), reverse=True)[8:]:
            old.unlink()
