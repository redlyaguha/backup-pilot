# BP-02 — подготовка, 30.10.2026

IN PROGRESS, не приёмка задачи.

Источник ISO: https://dl.astralinux.ru/astra/frozen/1.8_x86-64/1.8.1/iso/installation-1.8.1.6-27.06.2024_14.12.iso

Размер: 7013961728 байт, совпал с Content-Length.
Вычисленный SHA-256: `8810c6b12dae2fb63a7c3dc0d2df28cd1eaa5c6a35f2524935949d5b54ca43e8`.
Отдельная опубликованная контрольная сумма не получена.
`file`: ISO 9660, Astra 1.8_x86-64 amd64, bootable.
Live-консоль: Astra Linux 1.8.1.

ВМ UTM 4.7.5 / QEMU x86_64: q35, BIOS, 2 vCPU, 3072 МиБ RAM,
VirtIO 30 ГиБ, CD IDE. Целевой диск пуст; Live-режим не заменяет установленный стенд.

- sh -n обоих scripts/stand/*.sh: PASS на macOS.
- python3 scripts/check_repository.py: PASS, только структура.
- Установка на диск, версии Python/systemd, режим защищённости: NOT RUN.
- bpuser, права каталогов и запуск скриптов на установленной Astra: NOT RUN.
- Снимки clean-install и stand-ready: NOT RUN.

После установки выполнить admin-guide, приложить bp-02-stand.txt и обновить статус.
Не закрывать #2 по этому отчёту.
