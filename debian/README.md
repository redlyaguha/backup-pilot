# Debian-пакет

Первый `.deb` собирается в BP-17 без debhelper, через `dpkg-deb`.

## Файлы

- `control` — метаданные пакета (Package/Version/Architecture/Depends/Description).
- `postinst` — идемпотентное создание системного пользователя `backup-pilot`.
- `backup-pilot` — launcher, устанавливается как `/usr/bin/backup-pilot`.

## Сборка

```sh
sh scripts/package.sh
```

Скрипт собирает staging-дерево и кладёт результат в `dist/backup-pilot_<version>_amd64.deb`.
Версия читается из `src/backup_pilot/__init__.py` и сверяется с `control`.

## Состав пакета

- `/usr/bin/backup-pilot` — запускатель.
- `/usr/lib/backup-pilot/backup_pilot/` — код приложения.
- `/lib/systemd/system/backup-pilot@.service` и `backup-pilot@.timer` — шаблоны systemd.
- `/etc/backup-pilot/profiles.d/` — каталог именных TOML-профилей.
- `/var/lib/backup-pilot/` — служебные данные.

Политика обновления/удаления (conffiles, сохранение пользовательских копий) — в BP-20.
