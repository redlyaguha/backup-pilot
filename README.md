# Backup Pilot

Учебный менеджер резервного копирования для **Astra Linux Special Edition 1.8 x86-64**.
Кейс 04, проектный практикум МТУСИ. Имя Debian-пакета и команды: `backup-pilot`.

**Текущее состояние (BP-19):** Прототип реализован. Работают TOML-профили, копирование с исключениями, dry-run, контрольные суммы (manifest.json и verify), безопасное восстановление в новый каталог (restore), удаление старых копий (retention) и системное расписание (systemd). Собирается и устанавливается `.deb` пакет.

## Установка

### 1. Установка из `.deb` (для Astra Linux)
Пакет собирается скриптом и устанавливается через `apt`. Пользователю не требуются исходники, dev-venv или Интернет после установки.

```sh
# Сборка пакета (из корня репозитория)
sh scripts/package.sh

# Установка (потребуются права sudo)
sudo apt install ./dist/backup-pilot_0.1.0_amd64.deb

# Проверка
backup-pilot --version
backup-pilot --help
```

### 2. Запуск из исходников (для разработки)
Требуется Python 3.11+. Сторонние `pip`-пакеты не нужны.

```sh
PYTHONPATH=src python3 -B backup-pilot --help
```

## Быстрый старт (пример работы)

Ниже приведен базовый сценарий работы. Для примеров используется каталог `/tmp/bp-demo`.

```sh
# 1. Создайте тестовые данные и профиль
mkdir -p /tmp/bp-demo/source /tmp/bp-demo/backups
echo "hello" > /tmp/bp-demo/source/file.txt
echo "ignore" > /tmp/bp-demo/source/file.tmp

cat <<EOF > /tmp/bp-demo/demo.toml
name = "demo"
source = "/tmp/bp-demo/source"
destination = "/tmp/bp-demo/backups"
exclude = ["*.tmp"]
keep_last = 2
schedule = "daily"
EOF

# 2. Проверьте конфигурацию
backup-pilot --profiles-dir /tmp/bp-demo profiles validate --config /tmp/bp-demo/demo.toml

# 3. Сделайте пробный прогон (dry-run)
backup-pilot --profiles-dir /tmp/bp-demo run demo --dry-run

# 4. Создайте резервную копию
backup-pilot --profiles-dir /tmp/bp-demo run demo
# (Запомните ID снапшота из вывода, например: 20261128T...)

# 5. Проверьте целостность (сверка SHA-256)
backup-pilot --profiles-dir /tmp/bp-demo verify demo <ID_СНАПШОТА>

# 6. Восстановите в новый каталог
backup-pilot --profiles-dir /tmp/bp-demo restore demo <ID_СНАПШОТА> --to /tmp/bp-demo/restored

# 7. Очистите старые копии (оставит последние keep_last штук)
backup-pilot --profiles-dir /tmp/bp-demo prune demo --apply
```

## Ограничения и коды ошибок

Инструмент спроектирован безопасно, но имеет ограничения:
- Нет GUI, облачных хранилищ, шифрования и инкрементальных копий (только локальные полные копии).
- **Блокировки:** Одновременный запуск `run` и `prune` для одного профиля возвращает код `6` (профиль занят).
- **Безопасность:** Symlink и пути с `..` отклоняются. Восстановление (`restore`) пишет только в *новый* пустой каталог, существующие файлы не перезаписываются.

**Коды возврата (Exit codes):**
- `0` — Успех.
- `2` — Ошибка аргументов/конфигурации (например, битый TOML, неверный источник).
- `3` — Отказ доступа (нет прав на чтение/запись).
- `4` — Ошибка ввода-вывода (диск переполнен, сбой ОС).
- `5` — Нарушение целостности (поврежден `manifest.json` или файл данных).
- `6` — Профиль заблокирован другим процессом.

## Команда

| Участник | Ответственность |
|---|---|
| Рыбаченок Вадим (`@redlyaguha`) | Приложение, CLI, профили, копирование, retention, архитектура |
| Лихачев Алексей (`@LikhachevAlexey`) | Astra Linux, systemd, `.deb`, CI, релизы и GitFlic |
| Ушакова Ника (`@Nikii-fnchek`) | Проверка целостности, restore, тесты, документация пользователя и приёмка |

Все трое пишут код, тесты и участвуют в ревью. Подробности — [команда](docs/team.md).

## Работа с ветками

```text
dev → feature/BP-XX-task → PR в dev → ревью другого участника → merge в dev
dev → PR в prod → повторное ревью другого участника → merge в prod → release
```

`prod` — основная стабильная ветка; `dev` — интеграция разработки.
Код пишем в коротких ветках от `dev`. Прямые push в `dev` и `prod` запрещены.
Нужны одно одобрение другого участника, успешные обязательные проверки и закрытые обсуждения.

## Документация и CI

- [Общие требования из архива](docs/requirements/common.md) и [задание кейса](docs/requirements/case-04.md).
- [Архитектура и проектные интерфейсы](docs/architecture.md).
- [Руководство пользователя](docs/user-guide.md), [администратора](docs/admin-guide.md).
- [План и фактические результаты испытаний](docs/test-plan.md).

В этой ветке GitHub Actions проверяет структуру, направление PR и unit-тесты прототипа на Linux.
Скрипты `scripts/lint.sh`, `scripts/test.sh`, `scripts/package.sh` готовы к работе (локальный CI).
Настройка GitFlic и полного релизного CI — задача BP-23.

Unit-тесты запускаются отдельно:
`PYTHONPATH=src python3 -B -m unittest discover -s tests -v`.

Лицензия исходного кода — MIT.