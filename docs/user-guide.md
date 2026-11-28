# Руководство пользователя Backup Pilot

## Введение
Утилита предназначена для создания, проверки и восстановления локальных резервных копий. Работает от имени обычного пользователя. Требует Python 3.11+.

## Настройка профиля
Создайте файл `demo.toml` в каталоге `/etc/backup-pilot/profiles.d/` (или укажите свой через `--profiles-dir`). Все пути должны быть абсолютными.

```toml
name = "demo"
source = "/srv/backup-pilot-demo/source"
destination = "/srv/backup-pilot-demo/backups"
exclude = ["*.tmp", "cache/**"]
keep_last = 2
schedule = "Mon..Fri *-*-* 22:30:00"
```

## Команды и ожидаемый вывод

### 1. Проверка профиля
```sh
$ backup-pilot profiles validate --config /etc/backup-pilot/profiles.d/demo.toml
Профиль demo: OK
```
*Коды ошибок: 2 — неверный TOML/пути, 3 — нет прав на чтение.*

### 2. Сухой прогон (Dry-run)
Показывает, что будет скопировано, не создавая файлов.
```sh
$ backup-pilot run demo --dry-run
Назначение: "/srv/backup-pilot-demo/backups/demo"
mkdir "docs"
copy "docs/readme.txt"
copy "bin/sample.bin"
```

### 3. Создание резервной копии
```sh
$ backup-pilot run demo
Копирование завершено: /srv/backup-pilot-demo/backups/demo/20261128T120000123456Z-a1b2c3d4
SHA-256 записан в manifest.json.
```

### 4. Список копий
```sh
$ backup-pilot snapshots demo
20261128T120000123456Z-a1b2c3d4
```

### 5. Проверка целостности (Verify)
Сверяет SHA-256 всех файлов с `manifest.json`.
```sh
$ backup-pilot verify demo 20261128T120000123456Z-a1b2c3d4
Snapshot: OK
```
*Если файл поврежден — код 5 и сообщение `Integrity violation: hash mismatch`.*

### 6. Восстановление (Restore)
Восстанавливает в новый каталог. Существующий каталог перезаписывать нельзя.
```sh
$ backup-pilot restore demo 20261128T120000123456Z-a1b2c3d4 --to /tmp/restore_test
Restored to: /tmp/restore_test
```
*Флаг `--dry-run` покажет план, не создавая каталог. По умолчанию создаст `./restored/demo-<id>`.*

### 7. Очистка старых копий (Retention)
```sh
$ backup-pilot prune demo --dry-run
Удалить: "20261128T100000000000Z-b2c3d4e5"
```
```sh
$ backup-pilot prune demo --apply
Удалено: "20261128T100000000000Z-b2c3d4e5"
```

### 8. Расписание (Systemd)
```sh
$ backup-pilot schedule demo enable --dry-run
Установить OnCalendar="Mon..Fri *-*-* 22:30:00" в /etc/systemd/system/backup-pilot@demo.timer.d/50-backup-pilot-schedule.conf.
$ sudo backup-pilot schedule demo enable
backup-pilot@demo.timer: расписание включено.
```

## Ограничения и безопасность
- **Блокировки:** Одновременный запуск `run` и `prune` для одного профиля возвращает код `6` (профиль занят).
- **Безопасность:** Symlink и пути с `..` отклоняются.
- **Ошибки:** Нет прав — код 3. Ошибка ввода-вывода — код 4.