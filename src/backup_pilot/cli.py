"""The CLI delegates filesystem operations to services."""
import argparse
from pathlib import Path
import sys

from . import __version__
from .backup import execute_backup, list_snapshots, plan_backup, preview_lines
from .errors import BackupPilotError
from .profiles import list_profiles, load_named_profile, load_profile


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
    for name, help_text in (('run', 'создать отдельную копию'), ('snapshots', 'перечислить завершённые копии')):
        command = commands.add_parser(name, help=help_text)
        command.add_argument('profile', help='имя TOML-профиля без расширения')
        if name == 'run':
            command.add_argument('--dry-run', action='store_true', help='показать план без записи')
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'profiles':
            if args.operation == 'list':
                for profile in list_profiles(args.profiles_dir):
                    print(profile.name)
            else:
                profile = load_profile(args.config)
                print(f'Профиль {profile.name}: OK')
        else:
            profile = load_named_profile(args.profiles_dir, args.profile)
            if args.command == 'run':
                plan = plan_backup(profile)
                if args.dry_run:
                    print('\n'.join(preview_lines(plan)))
                else:
                    snapshot = execute_backup(plan)
                    print(f'Копирование завершено: {snapshot}')
                    print('SHA-256 ещё не проверен: модуль integrity — BP-09.')
            else:
                for snapshot in list_snapshots(profile):
                    print(snapshot.name)
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
