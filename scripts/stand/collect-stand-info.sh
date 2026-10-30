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
    echo
    echo "## Учебный пользователь"
    if id "$BP_USER" >/dev/null 2>&1; then
        echo "$BP_USER: uid=$(id -u "$BP_USER"), группы: $(id -nG "$BP_USER")"
        case " $(id -nG "$BP_USER") " in
            *" sudo "*|*" astra-admin "*|*" root "*)
                echo "Привилегии: FAIL (входит в административную группу)" ;;
            *)
                echo "Привилегии: OK (нет sudo/astra-admin/root)" ;;
        esac
    else
        echo "$BP_USER: NOT FOUND (запустите prepare-stand.sh --apply)"
    fi
    echo
    echo "## Учебные каталоги"
    for dir in "$BP_ROOT" "$BP_ROOT/source" "$BP_ROOT/backups"; do
        if [ -d "$dir" ]; then
            echo "$(stat -c '%A %U:%G' "$dir") $dir"
        else
            echo "NOT FOUND $dir"
        fi
    done
    if [ -d "$BP_ROOT/source" ] && [ -r "$BP_ROOT/source" ]; then
        echo
        echo "## Тестовые файлы source (SHA-256)"
        (cd "$BP_ROOT/source" && find . -type f | LC_ALL=C sort | xargs -r sha256sum)
    fi
}

report
