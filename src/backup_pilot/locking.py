"""Non-blocking profile operation lock; preview never enters this context."""
from contextlib import contextmanager
import os
import stat
from .errors import BackupPilotError
from .profiles import check_plain_path

@contextmanager
def profile_lock(profile):
    directory = profile.destination / '.backup-pilot-locks'
    check_plain_path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (profile.name + '.lock')
    check_plain_path(path)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    acquired = False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise BackupPilotError('Небезопасный файл блокировки.', 3)
        if os.name == 'nt':
            import msvcrt
            if info.st_size == 0:
                os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BackupPilotError('Профиль занят. Повторите позже.', 6) from exc
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BackupPilotError('Профиль занят. Повторите позже.', 6) from exc
        acquired = True
        yield
    finally:
        if acquired and os.name == 'nt':
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)
