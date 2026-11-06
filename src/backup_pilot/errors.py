"""Errors shared by CLI and services; codes 5 and 6 are reserved for later modules."""
import subprocess


class BackupPilotError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def user_error(exc: Exception) -> BackupPilotError:
    """Translate expected failures; never print external command output or a traceback."""
    if isinstance(exc, BackupPilotError):
        return exc
    if isinstance(exc, PermissionError):
        return BackupPilotError(f'Нет доступа: {exc.filename or "операция"}. Проверьте права пользователя.', 3)
    if isinstance(exc, FileNotFoundError):
        return BackupPilotError('Файл или команда не найдены. Проверьте пути и установленные зависимости.', 4)
    if isinstance(exc, subprocess.TimeoutExpired):
        return BackupPilotError('Внешняя команда не завершилась вовремя. Проверьте её состояние.', 4)
    if isinstance(exc, subprocess.CalledProcessError):
        return BackupPilotError(f'Внешняя команда завершилась с кодом {exc.returncode}. Проверьте её состояние.', 4)
    return BackupPilotError(f'Ошибка ввода-вывода: {exc}. Проверьте пути и свободное место.', 4)
