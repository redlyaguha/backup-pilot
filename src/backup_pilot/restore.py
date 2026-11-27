"""Restore verified snapshots into a new, separate directory."""
import hashlib
from pathlib import Path
import stat
from uuid import uuid4

from .errors import BackupPilotError
from .integrity import read_manifest, verify_snapshot
from .profiles import check_plain_path, validate_paths


def default_target(profile, snapshot_id):
    return Path.cwd() / 'restored' / f'{profile.name}-{snapshot_id}'


def _absolute_new_target(target):
    target = Path(target)
    if '..' in target.parts:
        raise BackupPilotError('Restore target must not contain "..".')
    return target.absolute()


def _validate_target(profile, target):
    target = _absolute_new_target(target)
    check_plain_path(target)
    if target.exists():
        raise BackupPilotError(f'Restore target already exists: {target}.')
    source = profile.source.resolve()
    destination = profile.destination.resolve()
    resolved = target.resolve(strict=False)
    if resolved.is_relative_to(source) or resolved.is_relative_to(destination):
        raise BackupPilotError('Restore target must be outside source and backup destination.')
    return target


def preview_restore(profile, snapshot_id, target):
    """Validate all read inputs without creating a directory or a lock file."""
    validate_paths(profile)
    target = _validate_target(profile, target)
    verify_snapshot(profile, snapshot_id)
    return target


def restore_snapshot(profile, snapshot_id, target):
    """Copy a verified snapshot into a new directory, then publish it atomically."""
    validate_paths(profile)
    target = _validate_target(profile, target)
    target = _validate_target(profile, target)
    verify_snapshot(profile, snapshot_id)
    snapshot, files = read_manifest(profile, snapshot_id)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    check_plain_path(target.parent)
    partial = target.parent / ('.partial-restore-' + uuid4().hex)
    partial.mkdir(mode=0o700)
    for item in files:
        relative = Path(item['path'])
        output = partial / relative
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _copy_verified(snapshot / 'data' / relative, output, item['sha256'])
    if target.exists():
        raise BackupPilotError(f'Restore target already exists: {target}.')
    partial.rename(target)
    return target


def _copy_verified(source, output, expected_hash):
    check_plain_path(source)
    if not stat.S_ISREG(source.lstat().st_mode):
        raise BackupPilotError('Integrity violation: restore source is not a regular file.', 5)
    digest = hashlib.sha256()
    with source.open('rb') as incoming, output.open('xb') as outgoing:
        for block in iter(lambda: incoming.read(1024 * 1024), b''):
            digest.update(block)
            outgoing.write(block)
    if digest.hexdigest() != expected_hash:
        raise BackupPilotError('Integrity violation: snapshot changed during restore.', 5)
