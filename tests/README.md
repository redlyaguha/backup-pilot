# Тесты продукта

Здесь находятся unit-тесты CLI, копирования и расписания.

Из корня, Python 3.11+ без дополнительных зависимостей:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -B -m unittest discover -s tests -v
```

`test_profiles`: TOML, типы, имена и пути. `test_backup`: байты, исключения,
несколько snapshot, partial и повреждённые метаданные. `test_dry_run`: отсутствие
записей и совпадение плана с реальным выполнением. `test_errors`: CLI, коды ошибок,
реальные Unix-права и symlink. `test_scheduler`: dry-run, календарь и откат при сбоях systemctl.
Linux-тесты выполняются обычным пользователем в Actions;
на Windows недоступные проверки имеют SKIP. Нельзя выдавать SKIP за PASS.

Сравнение дерева в dry-run включает байты, mtime и права, но не atime:
чтение каталогов/профиля может обновлять atime по политике самой файловой системы.
Dry-run не выполняет операций записи, не меняет systemd и не создаёт Python bytecode.
Приёмка A1–A5 и испытания Astra ведутся отдельно в `../docs/test-plan.md`.
