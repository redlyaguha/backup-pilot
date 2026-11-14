"""Verify snapshot integrity against manifest.json."""
import hashlib
import json
from pathlib import Path
import stat

from .errors import BackupPilotError
from .profiles import Profile, check_plain_path

def verify_snapshot(profile: Profile, snapshot_id: str) -> None:
    root = profile.destination / profile.name
    snapshot = root / snapshot_id
    
    if not snapshot.is_dir():
        raise BackupPilotError(f'Snapshot не найден: {snapshot_id}.', 2)
        
    manifest_path = snapshot / 'manifest.json'
    if not manifest_path.is_file():
        raise BackupPilotError(f'Отсутствует manifest.json в {snapshot_id}.', 5)

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise BackupPilotError(f'Некорректный manifest.json: {exc}.', 5) from exc

    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise BackupPilotError('Неверная версия схемы manifest.json.', 5)
        
    if manifest.get('profile') != profile.name or manifest.get('snapshot_id') != snapshot_id:
        raise BackupPilotError('Данные профиля или snapshot_id в manifest не совпадают.', 5)

    files = manifest.get('files', [])
    if not isinstance(files, list):
        raise BackupPilotError('Поле files в manifest должно быть списком.', 5)

    data_dir = snapshot / 'data'

    for item in files:
        if not isinstance(item, dict) or 'path' not in item or 'sha256' not in item:
            raise BackupPilotError('Неверный формат записи в manifest.json.', 5)
            
        rel_path = item['path']
        expected_hash = item['sha256']
        
        if not isinstance(rel_path, str) or '..' in rel_path.split('/') or rel_path.startswith('/'):
            raise BackupPilotError(f'Небезопасный путь в manifest: {rel_path}.', 5)
            
        file_path = data_dir / rel_path
        
        try:
            check_plain_path(file_path)
            mode = file_path.stat().st_mode
        except FileNotFoundError:
            raise BackupPilotError(f'Integrity violation: файл отсутствует {rel_path}.', 5)
            
        if not stat.S_ISREG(mode):
            raise BackupPilotError(f'Integrity violation: {rel_path} не является обычным файлом.', 5)

        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise BackupPilotError(f'Integrity violation: hash mismatch for {rel_path}.', 5)

    print(f'Snapshot {snapshot_id}: OK. Все файлы совпадают с manifest.')