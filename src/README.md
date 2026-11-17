# Исходный код

Python-пакет `backup_pilot/`, runtime — только стандартная библиотека Python 3.11+.
Из корня репозитория: `python3 -B backup-pilot --help`.
Для модульного запуска: `PYTHONPATH=src python3 -B -m backup_pilot --help`.
`--profiles-dir` указывается перед подкомандой; имя demo означает `demo.toml`.
Установка в PATH и `.deb` — отдельная задача BP-17.

- `cli.py`: argparse, вызов сервисов и диагностика. `__main__.py`: модульный вход.
- `profiles.py`: проверенный неизменяемый Profile, TOML и безопасные пути.
- `backup.py`: план без записи, выполнение плана, метаданные и список snapshot.
- `scheduler.py`: проверка OnCalendar, настройка таймера и откат при ошибке systemctl.
- `errors.py`: общая ошибка и перевод ожидаемых исключений в коды 2–6.

CLI не копирует файлы сам. Для dry-run и обычного запуска используется один BackupPlan.
Полные контракты для Ники и Алексея — в `../docs/architecture.md`.
