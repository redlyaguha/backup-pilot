# Руководство администратора

**Статус:** описано расписание BP-10. Упаковка и испытания пакета входят в BP-17 и BP-20–24.

Целевая среда — Astra Linux Special Edition 1.8 x86-64. Сначала подготовить отдельную чистую
ВМ со snapshot, учебного пользователя и тестовые source/destination. Записать версии ОС,
Python, systemd и Debian-инструментов, режим защищённости, права и ограничения стенда.

## Расписание systemd (BP-10)

Подготовьте доверенную установку CLI по пути `/usr/bin/backup-pilot` и установите
шаблоны `systemd/backup-pilot@.service` и `systemd/backup-pilot@.timer` в стандартный
каталог системных unit. Выполните `sudo systemctl daemon-reload`. Шаблон таймера
получает календарь при явном `schedule enable`.

Служба по умолчанию запускается как системный пользователь `backup-pilot`. Создайте
эту учётную запись при установке. На стенде можно назначить существующего
непривилегированного пользователя, например `bpuser`, через `User=bpuser` в drop-in
службы. Дайте этой учётной записи чтение профиля и источника и запись в каталог
назначения. Профили и unit держите под управлением root, без права записи для службы.

Для таймера используется профиль `/etc/backup-pilot/profiles.d/demo.toml` с
`name = "demo"`. Задайте поле `schedule` в формате OnCalendar, например
`schedule = "Mon..Fri *-*-* 22:30:00"`. Время без явного часового пояса трактуется
в часовом поясе стенда. Синтаксис проверяет `systemd-analyze calendar`.

```sh
backup-pilot schedule demo enable --dry-run
backup-pilot schedule demo status
sudo backup-pilot schedule demo enable
backup-pilot schedule demo status
sudo journalctl -u backup-pilot@demo.service
backup-pilot schedule demo disable --dry-run
sudo backup-pilot schedule demo disable
```

Статус показывает загрузку unit, состояние таймера, включение при загрузке,
календарь и ближайшее срабатывание. Пропущенные запуски при выключенной ВМ
не догоняются. Отключение останавливает будущие срабатывания и сохраняет
календарь. Уже запущенная копия завершается самостоятельно. Статус и отключение
доступны даже после удаления профиля.

После изменения `schedule` повторите `enable --dry-run`, затем `enable`.
Программа записывает календарь в
`/etc/systemd/system/backup-pilot@demo.timer.d/50-backup-pilot-schedule.conf`.
При ошибке systemctl она восстанавливает прежний drop-in и состояние таймера.
Если сам откат завершился ошибкой, проверьте `systemctl status` и сохранённое
расписание перед повтором. Для возврата к прежнему календарю после успешного
обновления верните прежнее значение в TOML и повторите `enable`.

Remove не удаляет резервные копии и чужие данные. Purge затрагивает только явно перечисленные
файлы пакета; пользовательские копии сохраняются. Это проектная политика, которую нужно
подтвердить реальными maintainer scripts и испытаниями.

CI: сначала локально работающие `scripts/lint.sh`, `test.sh`, `package.sh`, затем GitHub Actions
и GitFlic `lint → test → package` с `.deb` в artifacts. Секреты — только CI variables.
На GitFlic должны присутствовать `prod`, `dev` и финальные теги с теми же SHA, что на GitHub.
Контейнерные проверки дополняют, но не заменяют испытания systemd/пакета на Astra-ВМ.
