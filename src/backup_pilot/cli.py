"""The CLI delegates filesystem operations to services."""
import argparse
from pathlib import Path
import subprocess
import sys

from . import __version__
from .backup import execute_backup, list_snapshots, plan_backup, preview_lines
from .errors import BackupPilotError, user_error
from .profiles import list_profiles, load_named_profile, load_profile
from .scheduler import Scheduler, validate_calendar


DEFAULT_PROFILES_DIR = Path('/etc/backup-pilot/profiles.d')


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog='backup-pilot', description='Менеджер локальных резервных копий')
    result.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    result.add_argument('--profiles-dir', type=Path, default=DEFAULT_PROFILES_DIR,
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
    schedule = commands.add_parser('schedule', help='управлять системным расписанием профиля')
    schedule.add_argument('profile', help='имя системного TOML-профиля')
    schedule.add_argument('operation', choices=('status', 'enable', 'disable'))
    schedule.add_argument('--dry-run', action='store_true', help='показать план без изменений')
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
        elif args.command == 'schedule':
            if args.profiles_dir.absolute() != DEFAULT_PROFILES_DIR:
                raise BackupPilotError(f'Расписание использует системные профили в {DEFAULT_PROFILES_DIR}.')
            scheduler = Scheduler(args.profile)
            if args.operation == 'status':
                print(scheduler.status())
            else:
                calendar = (load_named_profile(args.profiles_dir, args.profile).schedule
                            if args.operation == 'enable' else None)
                if args.dry_run:
                    if calendar is not None:
                        calendar = validate_calendar(calendar)
                    print(scheduler.preview(calendar))
                else:
                    scheduler.apply(calendar)
                    print(f'{scheduler.timer}: расписание '
                          f'{"включено" if calendar is not None else "отключено"}.')
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
    except (BackupPilotError, OSError, subprocess.SubprocessError) as exc:
        error = user_error(exc)
        print(f'Ошибка: {error}', file=sys.stderr)
        return error.code
