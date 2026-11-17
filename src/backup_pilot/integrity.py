"""Validate completed snapshots and their SHA-256 manifests."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

from .errors import BackupPilotError
from .profiles import check_plain_path

ID = re.compile(r'\d{8}T\d{12}Z-[0-9a-f]{8}', re.ASCII)
HASH = re.compile(r'[0-9a-f]{64}', re.ASCII)


def read_manifest(profile, snapshot_id):
    if not isinstance(snapshot_id, str) or not ID.fullmatch(snapshot_id):
        raise BackupPilotError('Неверный ID завершённого snapshot.', 2)
    snapshot = profile.destination / profile.name / snapshot_id
    check_plain_path(snapshot)
    try:
        for path in (snapshot, snapshot / 'data'):
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise BackupPilotError('Snapshot/data должен быть обычным каталогом.', 5)
        for name in ('snapshot.json', 'manifest.json'):
            path = snapshot / name
            check_plain_path(path)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise BackupPilotError('Метаданные должны быть обычным файлом.', 5)
        metadata = json.loads((snapshot / 'snapshot.json').read_text(encoding='utf-8'))
        manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
        from datetime import datetime, timedelta
        for record in (metadata, manifest):
            if (not isinstance(record, dict) or type(record.get('schema_version')) is not int
                    or record['schema_version'] != 1 or record.get('profile') != profile.name
                    or record.get('snapshot_id') != snapshot_id):
                raise ValueError('metadata identity')
        stamp = datetime.fromisoformat(metadata['completed_at'])
        if stamp.utcoffset() != timedelta(0):
            raise ValueError('completion timestamp')
        files = manifest['files']
        if not isinstance(files, list):
            raise ValueError('files')
        seen = set()
        for item in files:
            if not isinstance(item, dict):
                raise ValueError('file entry')
            name, digest = item.get('path'), item.get('sha256')
            if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                    or '\x00' in name or name.startswith('/') or
                    any(p in ('', '.', '..') for p in name.split('/'))
                    or PurePosixPath(name).is_absolute() or name in seen
                    or not isinstance(digest, str) or not HASH.fullmatch(digest)):
                raise ValueError('file path/hash')
            seen.add(name)
        return snapshot, files
    except (FileNotFoundError, KeyError, ValueError, TypeError, UnicodeError) as exc:
        raise BackupPilotError('Некорректные или отсутствующие метаданные snapshot/manifest.', 5) from exc


def verify_snapshot(profile, snapshot_id):
    snapshot, files = read_manifest(profile, snapshot_id)
    for item in files:
        path = snapshot / 'data' / item['path']
        try:
            check_plain_path(path)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise BackupPilotError('Integrity violation: не обычный файл.', 5)
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != item['sha256']:
                raise BackupPilotError('Integrity violation: hash mismatch for ' + item['path'], 5)
        except FileNotFoundError as exc:
            raise BackupPilotError('Integrity violation: файл отсутствует ' + item['path'], 5) from exc
        except BackupPilotError as exc:
            raise BackupPilotError(str(exc), 5) from exc
    expected = {item['path'] for item in files}
    actual = set()
    for path in (snapshot / 'data').rglob('*'):
        check_plain_path(path)
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            actual.add(path.relative_to(snapshot / 'data').as_posix())
        elif not stat.S_ISDIR(mode):
            raise BackupPilotError('Integrity violation: специальный файл.', 5)
    if actual != expected:
        raise BackupPilotError('Integrity violation: список файлов не совпадает с manifest.', 5)
