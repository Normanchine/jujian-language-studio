"""Fail-closed JSON writes and verifiable, offline data snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

LOCK = threading.RLock()


def reject_links(root: Path) -> None:
    """Never copy or write through Windows reparse points (including junctions)."""
    import stat
    for path in [root, *root.rglob('*')]:
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0)
                                 & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise OSError('数据目录包含链接，请先移出链接：' + str(path))


def valid_relative(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    part = PurePosixPath(value)
    return (not part.is_absolute() and str(part) == value and all(
        p not in {'.', '..'} and not p.endswith((' ', '.')) and not PureWindowsPath(p).is_reserved()
        and not re.search(r'[\\\\:<>"|?*\x00-\x1f]', p) for p in part.parts))


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
                    if isinstance(old.get('items'), list) and any(not isinstance(item, dict) for item in old['items']):
                        raise ValueError('invalid collection entry')
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


def atomic_text(path: Path, value: str) -> None:
    """Small navigation pointers participate in the same snapshot lock."""
    path = Path(path)
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class DataStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.backups = self.root.with_name(self.root.name + '-backups')
        self.pending = self.backups / 'pending-restore.json'
        self.journal = self.backups / 'restore-journal.json'

    def snapshot(self, kind='manual') -> Path:
        with LOCK:
            if not re.fullmatch(r'[a-zA-Z0-9-]+', kind):
                raise OSError('备份类型无效')
            self.root.mkdir(parents=True, exist_ok=True)
            reject_links(self.root)
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
                if (not isinstance(manifest, dict) or type(manifest.get('format')) is not int
                        or manifest['format'] != 1 or not isinstance(manifest.get('files'), dict)
                        or not isinstance(manifest.get('source'), str) or not manifest['source']):
                    raise ValueError('不支持的备份格式')
                names = archive.namelist()
                expected = {'manifest.json'}
                total = 0
                normalized = set()
                for relative, info in manifest['files'].items():
                    if (not valid_relative(relative) or PurePosixPath(relative).suffix.lower() not in {'.json', '.txt'}
                            or relative.casefold() in normalized):
                        raise ValueError('备份包含非法路径')
                    normalized.add(relative.casefold())
                    if (not isinstance(info, dict) or type(info.get('size')) is not int or info['size'] < 0
                            or not isinstance(info.get('sha256'), str)
                            or not re.fullmatch('[0-9a-f]{64}', info['sha256'])):
                        raise ValueError('备份清单字段无效')
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
        except (KeyError, TypeError, ValueError, AttributeError, BadZipFile) as exc:
            raise OSError('备份无效：' + str(exc)) from exc

    def schedule_restore(self, name: str):
        path = self.backups / name
        if not valid_relative(name) or '/' in name or path.parent != self.backups or path.suffix != '.zip' or path.is_symlink():
            raise OSError('备份路径无效')
        manifest = self.verify(path)
        if Path(manifest['source']).resolve() != self.root:
            raise OSError('此备份属于另一个数据目录')
        atomic_json(self.pending, {'name': name, 'sha256': digest(path.read_bytes())})

    def recover_interrupted(self):
        """Roll back an interrupted directory swap before loading any bridges."""
        if not self.journal.exists():
            return
        try:
            state = json.loads(self.journal.read_text(encoding='utf-8'))
            old = Path(state['old'])
        except (ValueError, TypeError, KeyError) as exc:
            raise OSError('恢复日志损坏，已保留所有目录，请检查备份目录') from exc
        if old.parent != self.root.parent or not old.name.startswith(self.root.name + '-before-restore-'):
            raise OSError('恢复日志路径无效')
        if not self.root.exists() and (state.get('committed') is True or not old.exists()):
            raise OSError('恢复目录缺失，已停止启动并保留恢复日志')
        if state.get('committed') is True:
            self.pending.unlink(missing_ok=True)
            self.journal.unlink()
            return
        if old.exists():
            reject_links(old)
            if self.root.exists():
                self.root.rename(self.root.with_name(self.root.name + '-interrupted-' + uuid4().hex))
            old.rename(self.root)
        self.journal.unlink()

    def apply_pending(self) -> bool:
        with LOCK:
            self.recover_interrupted()
            if not self.pending.exists():
                return False
            try:
                request = json.loads(self.pending.read_text(encoding='utf-8'))
                name = request['name']
                if not valid_relative(name) or '/' in name or not name.endswith('.zip'):
                    raise ValueError('非法备份名称')
                if not isinstance(request.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', request['sha256']):
                    raise ValueError('非法备份校验值')
            except (ValueError, KeyError, TypeError) as exc:
                raise OSError('待恢复记录损坏，原数据未改变') from exc
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
                atomic_json(self.journal, {'old': str(old), 'committed': True})
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
            try:
                atomic_json(entry / 'entry.json', {'filename': source.name, 'deleted': datetime.now().isoformat(timespec='seconds')})
                source.rename(entry / 'content.json')
            except OSError:
                (entry / 'entry.json').unlink(missing_ok=True)
                entry.rmdir()
                raise
            return entry.name

    def restore_essay(self, entry_id: str):
        with LOCK:
            reject_links(self.root)
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
