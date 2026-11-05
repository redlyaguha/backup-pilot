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
import sys
root = Path(sys.argv[1])
if ('..' in root.parts or not root.is_absolute()
        or root == Path('/srv') or Path('/srv') not in root.parents):
    raise SystemExit('BP_ROOT: нужен подкаталог /srv без ..')
if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', sys.argv[2]) or sys.argv[2] == 'root':
    raise SystemExit('BP_USER: нужно имя отдельного учебного пользователя')
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

make_dir() { # путь владелец права
    if [ -d "$1" ]; then
        echo "каталог $1 уже существует, не изменяется"
        return
    fi
    step "install -d -o $2 -g $2 -m $3 $1"
    [ "$APPLY" -eq 0 ] || install -d -o "$2" -g "$2" -m "$3" "$1"
}

make_dir "$BP_ROOT" root 0755
make_dir "$SOURCE" "$BP_USER" 0750
make_dir "$BACKUPS" "$BP_USER" 0750
make_dir "$SOURCE/docs" "$BP_USER" 0750
make_dir "$SOURCE/cache" "$BP_USER" 0750
make_dir "$SOURCE/bin" "$BP_USER" 0750

# Тестовые данные: обычный файл и исключаемые *.tmp, cache/** для A1, бинарный файл для A4.
make_file() { # путь описание; содержимое читается из stdin
    if [ -e "$1" ]; then
        echo "файл $1 уже существует, не изменяется"
        cat >/dev/null
        return
    fi
    step "создать $1 ($2)"
    if [ "$APPLY" -eq 1 ]; then
        cat >"$1"
        chown "$BP_USER:$BP_USER" "$1"
        chmod 0640 "$1"
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
