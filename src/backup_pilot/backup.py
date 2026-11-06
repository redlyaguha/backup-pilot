"""Plan local copies, then publish completed snapshots by renaming a partial directory."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
import json
from pathlib import Path
import re
import shutil
import stat
from uuid import uuid4

from .errors import BackupPilotError
from .profiles import Profile, check_plain_path, validate_paths

SNAPSHOT_ID = re.compile(r'\d{8}T\d{12}Z-[0-9a-f]{8}', re.ASCII)


@dataclass(frozen=True)
class FileEntry:
    relative: Path
    signature: tuple[int, ...]


@dataclass(frozen=True)
class BackupPlan:
    profile: Profile
    directories: tuple[Path, ...]
    files: tuple[FileEntry, ...]


def file_signature(path: Path) -> tuple[int, ...]:
    check_plain_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise BackupPilotError(f'Поддерживаются только обычные файлы: {path}.')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def plan_backup(profile: Profile) -> BackupPlan:
    validate_paths(profile)
    directories = []
    files = []

    def excluded(relative: str) -> bool:
        return any(fnmatchcase(relative, pattern) for pattern in profile.exclude)

    def visit(directory: Path) -> None:
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(profile.source)
            if excluded(relative.as_posix()):
                continue
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                directories.append(relative)
                if not excluded(relative.as_posix() + '/'):
                    visit(path)
            elif stat.S_ISREG(mode):
                files.append(FileEntry(relative, file_signature(path)))
            else:
                raise BackupPilotError(f'Symlink и специальные файлы не поддерживаются: {path}. Исключите путь.')

    visit(profile.source)
    return BackupPlan(profile, tuple(sorted(directories, key=lambda p: p.as_posix())),
                      tuple(sorted(files, key=lambda f: f.relative.as_posix())))


def execute_backup(plan: BackupPlan) -> Path:
    profile = plan.profile
    validate_paths(profile)
    for relative in (*plan.directories, *(item.relative for item in plan.files)):
        if relative.is_absolute() or not relative.parts or '..' in relative.parts:
            raise BackupPilotError('Небезопасный относительный путь в плане копирования.')
    root = profile.destination / profile.name
    check_plain_path(root)
    snapshot_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-') + uuid4().hex[:8]
    partial = root / ('.partial-' + snapshot_id)
    snapshot = root / snapshot_id
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    partial.mkdir(mode=0o700)
    data = partial / 'data'
    data.mkdir(mode=0o700)
    for relative in plan.directories:
        source = profile.source / relative
        check_plain_path(source)
        if not stat.S_ISDIR(source.stat().st_mode):
            raise BackupPilotError(f'Исходный каталог изменился: {source}. Повторите запуск.', 4)
        (data / relative).mkdir(mode=0o700)
    for entry in plan.files:
        source = profile.source / entry.relative
        if file_signature(source) != entry.signature:
            raise BackupPilotError(f'Исходный файл изменился: {source}. Повторите запуск.', 4)
        shutil.copy2(source, data / entry.relative, follow_symlinks=False)
        if file_signature(source) != entry.signature:
            raise BackupPilotError(f'Исходный файл изменился при копировании: {source}. Повторите запуск.', 4)
    metadata = dict(schema_version=1, profile=profile.name, snapshot_id=snapshot_id,
                    completed_at=datetime.now(timezone.utc).isoformat())
    (partial / 'snapshot.json').write_text(json.dumps(metadata, ensure_ascii=False) + '\n', encoding='utf-8')
    if snapshot.exists():
        raise BackupPilotError('Коллизия имени snapshot. Частичная копия сохранена; повторите запуск.', 4)
    partial.rename(snapshot)
    return snapshot


def list_snapshots(profile: Profile) -> list[Path]:
    validate_paths(profile)
    root = profile.destination / profile.name
    check_plain_path(root)
    try:
        candidates = sorted(root.iterdir())
    except FileNotFoundError:
        return []
    result = []
    for path in candidates:
        if not SNAPSHOT_ID.fullmatch(path.name) or not stat.S_ISDIR(path.lstat().st_mode):
            continue
        try:
            if not stat.S_ISREG((path / 'snapshot.json').lstat().st_mode):
                continue
            if not stat.S_ISDIR((path / 'data').lstat().st_mode):
                continue
            metadata = json.loads((path / 'snapshot.json').read_text(encoding='utf-8'))
            if not isinstance(metadata, dict) or type(metadata.get('schema_version')) is not int:
                continue
            if (metadata['schema_version'] != 1 or metadata.get('profile') != profile.name
                    or metadata.get('snapshot_id') != path.name
                    or not isinstance(metadata.get('completed_at'), str)):
                continue
            completed = datetime.fromisoformat(metadata['completed_at'])
            if completed.utcoffset() != timedelta(0):
                continue
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError, ValueError):
            continue
        result.append(path)
    return result
