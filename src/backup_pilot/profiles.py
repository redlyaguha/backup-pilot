"""Load and validate TOML profiles without modifying the filesystem."""
from dataclasses import dataclass
from pathlib import Path
import re
import stat
import tomllib

from .errors import BackupPilotError

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}')


@dataclass(frozen=True)
class Profile:
    name: str
    source: Path
    destination: Path
    exclude: tuple[str, ...]
    keep_last: int
    schedule: str


def check_name(name: str) -> None:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise BackupPilotError('Имя профиля: 1–64 буквы/цифры ASCII, _ или -, первый символ — буква/цифра.')


def check_plain_path(path: Path) -> None:
    """Reject symlinks in existing components, including dangling links."""
    for part in (*reversed(path.parents), path):
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise BackupPilotError(f'Symlink не поддерживается: {part}. Укажите обычный путь.')


def validate_paths(profile: Profile) -> None:
    for path in (profile.source, profile.destination):
        if not path.is_absolute() or '..' in path.parts:
            raise BackupPilotError(f'Нужен абсолютный путь без ..: {path}. Исправьте профиль.')
        check_plain_path(path)
    source = profile.source.resolve()
    destination = profile.destination.resolve()
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise BackupPilotError('Источник и назначение совпадают или вложены друг в друга. Разделите каталоги.')
    try:
        source_mode = profile.source.stat().st_mode
    except FileNotFoundError as exc:
        raise BackupPilotError(f'Источник не существует: {profile.source}. Проверьте профиль.') from exc
    if not stat.S_ISDIR(source_mode):
        raise BackupPilotError(f'Источник должен быть каталогом: {profile.source}.')
    for part in (*reversed(profile.destination.parents), profile.destination):
        try:
            mode = part.stat().st_mode
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(mode):
            raise BackupPilotError(f'Назначение или его родитель — не каталог: {part}.')


def load_profile(path: Path) -> Profile:
    check_plain_path(path.absolute())
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise BackupPilotError(f'Профиль должен быть обычным файлом: {path}.', 2)
        with path.open('rb') as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise BackupPilotError(f'Профиль не найден: {path}. Проверьте --profiles-dir или --config.') from exc
    except (tomllib.TOMLDecodeError, UnicodeError) as exc:
        raise BackupPilotError(f'Некорректный TOML: {path}. Исправьте конфигурацию.') from exc
    required = {'name', 'source', 'destination', 'exclude', 'keep_last', 'schedule'}
    missing = required - data.keys()
    if missing:
        raise BackupPilotError('В профиле отсутствуют поля: ' + ', '.join(sorted(missing)))
    check_name(data['name'])
    for field in ('source', 'destination', 'schedule'):
        if not isinstance(data[field], str) or not data[field].strip() or '\x00' in data[field]:
            raise BackupPilotError(f'{field}: нужна непустая строка без NUL.')
    if type(data['keep_last']) is not int or data['keep_last'] < 1:
        raise BackupPilotError('keep_last: нужно целое число от 1, не bool.')
    patterns = data['exclude']
    if not isinstance(patterns, list) or any(
        not isinstance(item, str) or not item or item.startswith('/')
        or '\\' in item or '..' in item.split('/') or '\x00' in item or ':' in item
        for item in patterns
    ):
        raise BackupPilotError('exclude: нужен список непустых относительных glob без .. и обратного слеша.')
    profile = Profile(data['name'], Path(data['source']), Path(data['destination']),
                      tuple(patterns), data['keep_last'], data['schedule'])
    validate_paths(profile)
    return profile


def load_named_profile(directory: Path, name: str) -> Profile:
    check_name(name)
    profile = load_profile(directory / f'{name}.toml')
    if profile.name != name:
        raise BackupPilotError(f'Поле name должно совпадать с именем файла: {name}.toml.')
    return profile


def list_profiles(directory: Path) -> list[Profile]:
    check_plain_path(directory.absolute())
    try:
        paths = sorted(directory.iterdir())
    except FileNotFoundError as exc:
        raise BackupPilotError(f'Каталог профилей не найден: {directory}. Укажите --profiles-dir.') from exc
    return [load_named_profile(directory, path.stem) for path in paths if path.suffix == '.toml']
