#!/bin/sh
# Сбор версий и состояния учебного стенда Astra SE 1.8 (BP-02) в обезличенном виде:
# не выводит имя машины, сетевые адреса и учётные записи, кроме учебной. Ничего не меняет. Запускать с sudo, чтобы прочитать режим защищённости;
# без root соответствующие строки помечаются NOT RUN.
# Пример: sudo sh scripts/stand/collect-stand-info.sh > docs/evidence/bp-02-stand.txt
set -eu

BP_USER="${BP_USER:-bpuser}"
BP_ROOT="${BP_ROOT:-/srv/backup-pilot-demo}"

# Первая строка вывода команды либо пометка, почему результата нет.
first_line() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "NOT RUN (нет команды $1)"
        return
    fi
    out=$("$@" 2>&1) || { echo "ERROR (код $?): $(printf '%s\n' "$out" | head -n 1)"; return; }
    printf '%s\n' "$out" | head -n 1
}

as_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "NOT RUN (нужен sudo)"
    else
        first_line "$@"
    fi
}

os_field() {
    sed -n "s/^$1=//p" /etc/os-release | tr -d '"'
}

show_metadata() { # путь тип владелец права
    if [ -L "$1" ]; then
        echo "FAIL $1 (symlink)"
    elif [ ! -e "$1" ]; then
        echo "NOT FOUND $1"
    elif { [ "$2" = dir ] && [ ! -d "$1" ]; } || { [ "$2" = file ] && [ ! -f "$1" ]; }; then
        echo "FAIL $1 (неожиданный тип объекта)"
    else
        actual=$(stat -c '%U:%G %a' -- "$1")
        if [ "$actual" = "$3:$3 $4" ]; then
            echo "OK $actual $1"
        else
            echo "FAIL $actual $1 (ожидается $3:$3 $4)"
        fi
    fi
}

report() {
    echo "# Backup Pilot — стенд BP-02"
    echo "Собрано (UTC): $(date -u '+%Y-%m-%d %H:%M')"
    echo
    echo "## Система"
    if [ -r /etc/astra/build_version ]; then
        echo "Astra build_version: $(head -n 1 /etc/astra/build_version)"
    else
        echo "Astra build_version: NOT FOUND (/etc/astra/build_version отсутствует)"
    fi
    if [ -r /etc/os-release ]; then
        echo "OS: $(os_field PRETTY_NAME) (VERSION_ID=$(os_field VERSION_ID))"
    fi
    echo "Ядро: $(uname -r), архитектура: $(uname -m)"
    echo "Виртуализация: $(first_line systemd-detect-virt)"
    if [ -d /sys/firmware/efi ]; then echo "Загрузка: UEFI"; else echo "Загрузка: BIOS"; fi
    echo "Корневая ФС: $(first_line findmnt -n -o SOURCE,FSTYPE /)"
    case "$(findmnt -n -o FSTYPE /)" in
        overlay|squashfs) echo "Загрузка с диска: FAIL (Live root)" ;;
        *) echo "Загрузка с диска: проверить SOURCE выше, ожидается /dev/vda2 ext4" ;;
    esac
    echo "Режим защищённости: $(as_root astra-modeswitch getname)"
    echo
    echo "## Инструменты"
    echo "Python: $(first_line python3 --version)"
    if python3 -c 'import tomllib' 2>/dev/null; then
        echo "tomllib: OK"
    else
        echo "tomllib: FAIL (нужен Python 3.11+)"
    fi
    echo "systemd: $(first_line systemctl --version)"
    echo "dpkg: $(first_line dpkg --version)"
    echo "dpkg-deb: $(first_line dpkg-deb --version)"
    echo "apt: $(first_line apt --version)"
    audit=$(dpkg --audit 2>&1) || audit="ERROR: $audit"
    if [ -z "$audit" ]; then echo "dpkg audit: OK (нет незавершённых пакетов)";
    else echo "dpkg audit: FAIL $audit"; fi
    echo
    echo "## Учебный пользователь"
    if id "$BP_USER" >/dev/null 2>&1; then
        echo "$BP_USER: uid=$(id -u "$BP_USER"), группы: $(id -nG "$BP_USER")"
        if [ "$(id -u "$BP_USER")" -ne 0 ] && [ "$(id -nG "$BP_USER")" = "$BP_USER" ]; then
            echo "Привилегии: OK (ненулевой uid, только учебная группа)"
        else
            echo "Привилегии: FAIL (ожидается непривилегированный uid и только учебная группа)"
        fi
    else
        echo "$BP_USER: NOT FOUND (запустите prepare-stand.sh --apply)"
    fi
    echo
    echo "## Учебные каталоги и права"
    show_metadata "$BP_ROOT" dir root 755
    for suffix in source backups source/docs source/cache source/bin; do
        show_metadata "$BP_ROOT/$suffix" dir "$BP_USER" 750
    done
    echo
    echo "## Учебные файлы и права"
    for suffix in docs/readme.txt notes.tmp cache/item.txt bin/sample.bin; do
        show_metadata "$BP_ROOT/source/$suffix" file "$BP_USER" 640
    done
    if [ -d "$BP_ROOT/source" ] && [ -r "$BP_ROOT/source" ]; then
        echo
        echo "## Тестовые файлы source (SHA-256)"
        hash_source='cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0r sha256sum'
        if [ "$(id -u)" -eq 0 ]; then
            runuser -u "$BP_USER" -- /bin/sh -c "$hash_source" _ "$BP_ROOT/source" ||
                echo "FAIL (не удалось собрать SHA-256 от имени $BP_USER)"
        else
            /bin/sh -c "$hash_source" _ "$BP_ROOT/source" ||
                echo "FAIL (не удалось собрать SHA-256)"
        fi
    fi
}

report
