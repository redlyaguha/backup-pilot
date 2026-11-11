"""Configure one systemd timer per profile using an owned calendar drop-in."""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from .errors import BackupPilotError, user_error
from .profiles import check_name, check_plain_path

SYSTEM_UNITS = Path('/etc/systemd/system')
SYSTEMCTL = '/usr/bin/systemctl'
ANALYZE = '/usr/bin/systemd-analyze'
DROP_IN = '50-backup-pilot-schedule.conf'
STATE_FIELDS = ('LoadState', 'ActiveState', 'UnitFileState')
STATUS_FIELDS = (*STATE_FIELDS, 'TimersCalendar', 'NextElapseUSecRealtime')


def validate_calendar(value: str) -> str:
    if any(not 32 <= ord(char) <= 126 or char in '%\\' for char in value):
        raise BackupPilotError('OnCalendar должен быть одной строкой без управляющих символов, % и обратной косой черты.')
    value = value.strip()
    if not value:
        raise BackupPilotError('OnCalendar не может быть пустым.')
    result = subprocess.run(
        [ANALYZE, '--no-pager', 'calendar', '--', value],
        capture_output=True, timeout=15,
    )
    if result.returncode:
        raise BackupPilotError('Неверное расписание OnCalendar. Проверьте поле schedule в профиле.')
    return value


@dataclass(frozen=True)
class DropInState:
    content: bytes | None
    mode: int
    directory_existed: bool


def read_drop_in(path: Path) -> DropInState:
    check_plain_path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return DropInState(None, 0o644, path.parent.is_dir())
    if not stat.S_ISREG(info.st_mode):
        raise BackupPilotError(f'Настройка расписания должна быть обычным файлом: {path}.')
    return DropInState(path.read_bytes(), stat.S_IMODE(info.st_mode), True)


def write_drop_in(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(mode=0o755, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.bp-schedule-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


class Scheduler:
    def __init__(self, profile: str, unit_dir: Path = SYSTEM_UNITS):
        check_name(profile)
        self.service = f'backup-pilot@{profile}.service'
        self.timer = f'backup-pilot@{profile}.timer'
        self.drop_in = unit_dir / f'{self.timer}.d' / DROP_IN
        self.unit_dir = unit_dir

    @staticmethod
    def _systemctl(*args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [SYSTEMCTL, '--no-pager', '--no-ask-password', *args],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        )
        if result.returncode:
            operation = args[0] if args[0] != '--no-reload' else args[1]
            raise BackupPilotError(
                f'systemctl {operation} завершился с кодом {result.returncode}. '
                'Проверьте состояние systemd, установку unit и права администратора.', 4,
            )
        return result

    def _properties(self, unit: str, fields: tuple[str, ...]) -> dict[str, str]:
        output = self._systemctl('show', f'--property={",".join(fields)}', '--', unit).stdout
        return dict(line.split('=', 1) for line in output.splitlines() if '=' in line)

    def status(self) -> str:
        properties = self._properties(self.timer, STATUS_FIELDS)
        return '\n'.join([self.timer, *(
            f'{key}={json.dumps(properties.get(key, ""), ensure_ascii=True)}' for key in STATUS_FIELDS
        )])

    def preview(self, calendar: str | None) -> str:
        if calendar is None:
            return f'Остановить и отключить {self.timer}. Сохранить файл расписания.'
        return (
            f'Установить OnCalendar={json.dumps(calendar)} в {self.drop_in}.\n'
            f'Перечитать конфигурацию systemd, включить и запустить {self.timer}.'
        )

    @contextmanager
    def _lock(self):
        if not hasattr(os, 'geteuid') or os.geteuid() != 0:
            raise BackupPilotError('Для изменения системного таймера нужны права администратора. Используйте sudo.', 3)
        import fcntl
        check_plain_path(self.unit_dir)
        descriptor = os.open(self.unit_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BackupPilotError('Расписание уже меняется. Повторите команду позже.', 6) from exc
            yield
        finally:
            os.close(descriptor)

    def apply(self, calendar: str | None) -> None:
        if calendar is not None:
            calendar = validate_calendar(calendar)
        with self._lock():
            state = self._properties(self.timer, STATE_FIELDS)
            if state.get('LoadState') not in ('loaded', 'bad-setting'):
                raise BackupPilotError(f'Таймер {self.timer} недоступен. Проверьте установку шаблонов.', 4)
            active = state.get('ActiveState')
            enabled = state.get('UnitFileState')
            if active not in ('active', 'inactive', 'failed') or enabled not in ('enabled', 'disabled'):
                raise BackupPilotError(
                    f'Таймер {self.timer} не в устойчивом состоянии active/inactive/failed и enabled/disabled. '
                    'Проверьте systemctl status и повторите команду.', 4,
                )
            if calendar is None and active == 'inactive' and enabled == 'disabled':
                return
            if calendar is not None:
                service = self._properties(self.service, ('LoadState',))
                if service.get('LoadState') != 'loaded':
                    raise BackupPilotError(f'Служба {self.service} недоступна. Установите шаблон службы.', 4)
            previous = read_drop_in(self.drop_in) if calendar is not None else None
            changed = False
            try:
                if active == 'active':
                    self._systemctl('stop', '--', self.timer)
                if calendar is not None:
                    changed = True
                    content = f'[Timer]\nOnCalendar=\nOnCalendar={calendar}\n'.encode('ascii')
                    write_drop_in(self.drop_in, content, previous.mode)
                    self._systemctl('daemon-reload')
                operation = 'enable' if calendar is not None else 'disable'
                self._systemctl('--no-reload', operation, '--', self.timer)
                if calendar is not None:
                    self._systemctl('start', '--', self.timer)
            except (BackupPilotError, OSError, subprocess.SubprocessError) as exc:
                error = user_error(exc)
                try:
                    self._rollback(active, enabled, previous if changed else None)
                except (BackupPilotError, OSError, subprocess.SubprocessError) as rollback:
                    raise BackupPilotError(
                        f'{error} Откат не завершён: {user_error(rollback)} Проверьте {self.timer} вручную.',
                        error.code,
                    ) from exc
                raise BackupPilotError(f'{error} Прежнее расписание восстановлено.', error.code) from exc

    def _rollback(self, active: str, enabled: str, previous: DropInState | None) -> None:
        state = self._properties(self.timer, STATE_FIELDS)
        if state.get('ActiveState') != 'inactive':
            self._systemctl('stop', '--', self.timer)
        if previous is not None:
            if previous.content is None:
                self.drop_in.unlink(missing_ok=True)
                directory = self.drop_in.parent
                if not previous.directory_existed and directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            else:
                write_drop_in(self.drop_in, previous.content, previous.mode)
            self._systemctl('daemon-reload')
        operation = 'enable' if enabled == 'enabled' else 'disable'
        self._systemctl('--no-reload', operation, '--', self.timer)
        if active == 'active':
            self._systemctl('start', '--', self.timer)
