#!/bin/sh
# Подготовка учебного стенда Astra SE 1.8 для Backup Pilot (BP-02).
# Без аргументов только показывает план; изменения выполняются с --apply от root.
# Повторный запуск безопасен: существующие пользователь, каталоги и файлы не перезаписываются.
set -eu

BP_USER="${BP_USER:-bpuser}"
BP_ROOT="${BP_ROOT:-/srv/backup-pilot-demo}"
SOURCE="$BP_ROOT/source"
BACKUPS="$BP_ROOT/backups"

usage() {
    echo "Использование: $0 [--apply]" >&2
    echo "  без аргументов  показать план, ничего не меняя" >&2
    echo "  --apply         выполнить подготовку (нужен root)" >&2
    echo "Переменные: BP_USER (по умолчанию bpuser), BP_ROOT (по умолчанию /srv/backup-pilot-demo)" >&2
}

[ "$#" -le 1 ] || { usage; exit 2; }

APPLY=0
case "${1:-}" in
    "") ;;
    --apply) APPLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
esac

fail() { echo "ошибка: $1" >&2; exit "${2:-1}"; }
step() {
    if [ "$APPLY" -eq 1 ]; then echo "+ $*"; else echo "[план] $*"; fi
}

[ "$(uname -s)" = Linux ] || fail "стенд готовится только на Linux" 2
case "$BP_ROOT" in
    /srv/*) ;;
    *) fail "BP_ROOT должен лежать в /srv: учебные данные не смешиваются с системными" 2 ;;
esac
if [ ! -r /etc/astra/build_version ] && [ "${BP_ALLOW_NON_ASTRA:-0}" != 1 ]; then
    fail "/etc/astra/build_version не найден: это не Astra Linux (для проверки скрипта: BP_ALLOW_NON_ASTRA=1)" 2
fi
if [ "$APPLY" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
    fail "--apply требует root: sudo $0 --apply" 3
fi
command -v python3 >/dev/null 2>&1 || fail "не найден python3, нужен для учебного бинарного файла" 4

# Проверить пути до любых изменений от root: /srv/../... и symlink недопустимы.
python3 - "$BP_ROOT" "$BP_USER" <<'CHECK_PATHS' || fail "небезопасные параметры стенда" 2
from pathlib import Path
import re
import stat
import sys
root = Path(sys.argv[1])
if ('..' in root.parts or not root.is_absolute()
        or root == Path('/srv') or Path('/srv') not in root.parents):
    raise SystemExit('BP_ROOT: нужен подкаталог /srv без ..')
if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', sys.argv[2]) or sys.argv[2] == 'root':
    raise SystemExit('BP_USER: нужно имя отдельного учебного пользователя')
# Только root может менять компоненты пути до корня учебного стенда.
for part in (*reversed(root.parents), root):
    try:
        info = part.lstat()
    except FileNotFoundError:
        continue
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise SystemExit('Нужен каталог root без записи для группы и остальных: ' + str(part))
for suffix in ('', 'source', 'backups', 'source/docs', 'source/cache', 'source/bin',
               'source/docs/readme.txt', 'source/notes.tmp', 'source/cache/item.txt',
               'source/bin/sample.bin'):
    path = root / suffix
    if any(part.is_symlink() for part in (*path.parents, path)):
        raise SystemExit('Symlink в учебном пути: ' + str(path))
CHECK_PATHS

# Пользователь без пароля и без административных групп: вход только через sudo -iu.
if id "$BP_USER" >/dev/null 2>&1; then
    echo "пользователь $BP_USER уже существует, не изменяется"
else
    step "useradd --create-home --user-group --shell /bin/bash $BP_USER"
    [ "$APPLY" -eq 0 ] || useradd --create-home --user-group --shell /bin/bash "$BP_USER"
fi

# Существующая учётная запись тоже должна быть отдельной и непривилегированной.
if id "$BP_USER" >/dev/null 2>&1; then
    [ "$(id -u "$BP_USER")" -ne 0 ] && [ "$(id -nG "$BP_USER")" = "$BP_USER" ] ||
        fail "пользователь $BP_USER должен иметь ненулевой uid и только группу $BP_USER" 2
fi

check_metadata() { # путь владелец права
    actual=$(stat -c '%U:%G %a' -- "$1") || fail "не удалось прочитать права $1" 2
    [ "$actual" = "$2:$2 $3" ] ||
        fail "$1: получено $actual, ожидается $2:$2 $3" 2
}

make_dir() { # путь владелец права [user]
    [ ! -L "$1" ] || fail "symlink вместо каталога: $1" 2
    if [ -e "$1" ]; then
        [ -d "$1" ] || fail "ожидается каталог: $1" 2
        check_metadata "$1" "$2" "$3"
        echo "каталог $1 уже существует, не изменяется"
        return
    fi
    if [ "${4:-}" = user ]; then
        step "runuser -u $BP_USER -- mkdir -m $3 $1"
        [ "$APPLY" -eq 0 ] || runuser -u "$BP_USER" -- mkdir -m "$3" -- "$1"
    else
        step "install -d -o $2 -g $2 -m $3 $1"
        [ "$APPLY" -eq 0 ] || install -d -o "$2" -g "$2" -m "$3" -- "$1"
    fi
    [ "$APPLY" -eq 0 ] || check_metadata "$1" "$2" "$3"
}

make_dir "$BP_ROOT" root 755
make_dir "$SOURCE" "$BP_USER" 750
make_dir "$BACKUPS" "$BP_USER" 750
make_dir "$SOURCE/docs" "$BP_USER" 750 user
make_dir "$SOURCE/cache" "$BP_USER" 750 user
make_dir "$SOURCE/bin" "$BP_USER" 750 user

# В дереве source все записи выполняет учебный пользователь.
make_file() { # путь описание; содержимое читается из stdin
    [ ! -L "$1" ] || fail "symlink вместо файла: $1" 2
    if [ -e "$1" ]; then
        [ -f "$1" ] || fail "ожидается обычный файл: $1" 2
        check_metadata "$1" "$BP_USER" 640
        echo "файл $1 уже существует, не изменяется"
        cat >/dev/null
        return
    fi
    step "создать $1 от имени $BP_USER ($2)"
    if [ "$APPLY" -eq 1 ]; then
        runuser -u "$BP_USER" -- /bin/sh -c 'umask 027; set -C; cat > "$1"' _ "$1"
        check_metadata "$1" "$BP_USER" 640
    else
        cat >/dev/null
    fi
}

printf 'Учебный файл Backup Pilot: должен попасть в копию.\n' |
    make_file "$SOURCE/docs/readme.txt" "обычный файл"
printf 'Временный файл: исключается правилом *.tmp.\n' |
    make_file "$SOURCE/notes.tmp" "исключается *.tmp"
printf 'Кэш: исключается правилом cache/**.\n' |
    make_file "$SOURCE/cache/item.txt" "исключается cache/**"
# Детерминированные 64 КиБ всех значений байта: одинаковый SHA-256 на любом стенде.
python3 -c 'import sys; sys.stdout.buffer.write(bytes(range(256)) * 256)' |
    make_file "$SOURCE/bin/sample.bin" "бинарный файл 64 КиБ"

if [ "$APPLY" -eq 1 ]; then
    echo "стенд подготовлен: $BP_ROOT, пользователь $BP_USER"
    echo "проверка: sh scripts/stand/collect-stand-info.sh"
else
    echo "изменения не выполнялись; для подготовки: sudo $0 --apply"
fi
