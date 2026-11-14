# BP-02 — подготовка и восстановление, 05.11.2026

Технические критерии BP-02 проверены на установленной Astra 05.11.2026.
Ревью и слияние PR ещё требуются; этот отчёт не закрывает issue сам по себе.

Источник ISO: https://dl.astralinux.ru/astra/frozen/1.8_x86-64/1.8.1/iso/installation-1.8.1.6-27.06.2024_14.12.iso

Размер: 7013961728 байт, совпал с Content-Length.
Вычисленный SHA-256: `8810c6b12dae2fb63a7c3dc0d2df28cd1eaa5c6a35f2524935949d5b54ca43e8`.
Отдельная опубликованная контрольная сумма не получена.
`file`: ISO 9660, Astra 1.8_x86-64 amd64, bootable.
Live-консоль: Astra Linux 1.8.1.

Фактическая ВМ UTM 4.7.5 / QEMU x86_64: q35, UEFI, 1 vCPU, 2048 МиБ RAM,
VirtIO 30 ГиБ, CD IDE, SSH только `127.0.0.1:2223 → 22`.
На диске уже есть GPT: EFI 600 МиБ и ext4 29.4 ГиБ. Установка прервалась при
настройке модулей ядра (37%); перед восстановлением 05.11 сохранён отдельный
остановленный клон `BP-02-interrupted-install`. Восстановление завершено без форматирования: dpkg, пакеты Parsec для штатного PAM,
UEFI GRUB, режим Orel, SSH и sudo. Затем проверена загрузка с единственным диском, без CD.

Исходный ISO неизменён. Производный загрузочный ISO воспроизводится скриптом
`scripts/stand/make-utm-live-iso.py`; изменены только строки EFI GRUB по смещениям
9113447 и 7006336871. SHA-256 производного ISO:
`5ea32fb48e9997d7d5a16cbbfffcc1f7c74860abfa54a3ca9a9bfdef058b4119`.
Live-параметры: `boot=live noapic console=ttyS0,115200n8 systemd.debug_shell=ttyS0 systemd.unit=multi-user.target`.
QEMU: `-machine i8042=on,hpet=on`. `noapic` устранил сбой IO-APIC timer.
Временные monitor/VNC слушали только loopback. Live не считается установленным стендом.

- sh -n обоих scripts/stand/*.sh: PASS на macOS.
- Создание производного ISO штатным скриптом: PASS, полный исходный SHA-256 проверен.
- План prepare-stand на Live Astra: exit 0, без изменений.
- Попытки --apply с BP_ROOT=/srv/../tmp и symlink: обе exit 2 до записи.
- python3 scripts/check_repository.py: PASS, только структура.
- Загрузка без CD: PASS, QEMU имеет только системный диск; `lsblk` — только vda1/vda2.
- На установленной ОС: Astra 1.8.1.6, generic 6.1.90-1, x86_64, UEFI, `base(orel)`.
- Фактические версии Python/systemd/dpkg/apt и хэши исходных файлов: `bp-02-stand.txt`.
- prepare-stand: план и --apply exit 0. Повторный --apply exit 0; inode, владелец,
  права, mtime и содержимое всех учебных объектов не изменились.
- bpuser: uid 1001, только группа bpuser, пароль L; source доступен для чтения,
  backups для записи, /etc недоступен для записи.
- Незавершённых пакетов и упавших системных служб после контрольной загрузки нет.
- clean-install: сохранён остановленный клон после проверки входа SSH/sudo, без исходников
  проекта, bpuser и учебных данных.
- stand-ready: сохранён остановленный клон после подготовки, до первого backup;
  destination пуст. Оба клона подтверждены `utmctl list` со статусом stopped.

Исходный ISO без изменений; сетевые обновления, Hardened и режимы 1/2 не проверялись.
Фактическая конфигурация отличается от исходного плана BIOS/2CPU/3ГБ; выше записан
реально проверенный вариант UEFI/1CPU/2ГиБ с noapic.
