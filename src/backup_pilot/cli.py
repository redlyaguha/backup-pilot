"""The CLI delegates filesystem operations to services."""
import argparse
from pathlib import Path
import sys

from . import __version__
from .errors import BackupPilotError
from .profiles import list_profiles, load_profile


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog='backup-pilot', description='Менеджер локальных резервных копий')
    result.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    result.add_argument('--profiles-dir', type=Path, default=Path('/etc/backup-pilot/profiles.d'),
                        help='каталог именных TOML-профилей')
    commands = result.add_subparsers(dest='command', required=True)
    profiles = commands.add_parser('profiles', help='список и проверка профилей')
    operations = profiles.add_subparsers(dest='operation', required=True)
    operations.add_parser('list', help='показать профили')
    validate = operations.add_parser('validate', help='проверить TOML без записи')
    validate.add_argument('--config', required=True, type=Path)
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.operation == 'list':
            for profile in list_profiles(args.profiles_dir):
                print(profile.name)
        else:
            profile = load_profile(args.config)
            print(f'Профиль {profile.name}: OK')
        return 0
    except BackupPilotError as exc:
        print(f'Ошибка: {exc}', file=sys.stderr)
        return exc.code
    except PermissionError as exc:
        print(f'Ошибка доступа: {exc.filename or "путь"}. Проверьте права пользователя.', file=sys.stderr)
        return 3
    except OSError as exc:
        print(f'Ошибка ввода-вывода: {exc}. Проверьте пути и свободное место.', file=sys.stderr)
        return 4
