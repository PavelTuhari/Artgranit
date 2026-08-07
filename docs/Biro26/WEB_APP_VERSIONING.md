# Версия веб-приложения — правило обновления

Номер версии виден в подвале сайта, сразу после `UNA.md and ORACLE OCI based`:

```
© 2026 Office Plus. Toate drepturile rezervate. · UNA.md and ORACLE OCI based v2026.08.08
```

## Правило

**Номер версии — это дата релиза в формате `YYYY.MM.DD`.** Никакой семантики
вроде `1.4.2`: раз выкатили — версия равна сегодняшней дате.

**Одно и то же значение записывается в ОБЕ базы:**

| База | Таблица | Где живёт |
|---|---|---|
| Oracle (OfficePlus 11g) | `TMS_WEBAPPVERS` | схема `OFFICEPLUS` |
| MySQL (WordPress) | `tms_webappvers` | база `officeplus_wp` |

Смысл дублирования — не запасная копия, а **контроль синхронности**. Oracle и
MySQL живут отдельно, и если в одной из них версия отстала, значит выкатили
только половину. Расхождение видно одной командой:

```bash
python scripts/set_app_version.py --show
```

Дополнительно версия кладётся в `wp_options.officeplus_app_version` — оттуда её
может брать WordPress-часть сайта.

## Как обновлять

Одна команда, после каждого релиза:

```bash
python scripts/set_app_version.py --note "коротко, что выкатили"
```

Она сама подставит сегодняшнюю дату и запишет в Oracle и в MySQL. Варианты:

```bash
python scripts/set_app_version.py --show                    # что записано сейчас
python scripts/set_app_version.py --version 2026.08.10      # задать вручную
python scripts/set_app_version.py --app wordpress           # только WordPress
python scripts/set_app_version.py --hash                    # + контрольная сумма исходников
python scripts/set_app_version.py --oracle-only             # если MySQL недоступен
```

Реквизиты MySQL скрипт читает из `wp-config.php`
(`/var/www/officeplus/wp-config.php` на новом сервере) — пароль нигде не
хранится и не передаётся в командной строке, только через `MYSQL_PWD`.

## Поле SRC_HASH — контрольные суммы

Колонка `SRC_HASH VARCHAR2(64)` заведена под **SHA-256 исходников проекта**.
Сейчас заполняется по желанию (флаг `--hash`), в будущем — чтобы отслеживать,
какой именно код развёрнут, и ловить расхождение между тем, что в git, и тем,
что на сервере.

Что входит в сумму: `*.py`, `templates/**/*.html`, `static/**/*.js`,
`static/**/*.css`, `sql/**/*.sql`. Исключены `venv`, `__pycache__`, `.git`,
`backups`, `AccountingDemoXcode`, `node_modules`. Хэш считается по паре
«относительный путь + содержимое», файлы сортируются — значит он воспроизводим
на любой машине.

Проверить, совпадает ли развёрнутый код с записанным:

```bash
python scripts/set_app_version.py --hash          # печатает сумму
python scripts/set_app_version.py --show          # показывает сохранённую
```

## Структура таблицы

Одинаковая в обеих базах:

| Колонка | Смысл |
|---|---|
| `ID` | суррогатный ключ (Oracle — последовательность + триггер, MySQL — `AUTO_INCREMENT`) |
| `APP_CODE` | `site` (Flask) или `wordpress` |
| `VERS` | `YYYY.MM.DD` — номер версии |
| `IS_CURRENT` | `'1'` у действующей записи, `'0'` у истории |
| `SRC_HASH` | SHA-256 исходников |
| `NOTE` | комментарий к релизу |
| `RELEASED`, `CREATED` | даты |

История **не удаляется**: при новом релизе прежняя строка получает
`IS_CURRENT = '0'`, а новая вставляется рядом. Уникальный индекс гарантирует,
что действующая запись у приложения ровно одна: в Oracle через
`CASE WHEN IS_CURRENT='1' THEN '1' END` (NULL не индексируются), в MySQL —
через сгенерированную колонку `cur_key` с той же логикой.

Читать текущую версию удобнее через представление `VMS_WEBAPPVERS` (Oracle)
или `WHERE is_current='1'` (MySQL).

## Откуда версия попадает в подвал

`models/biro26_version.py` → `current()` читает `VMS_WEBAPPVERS` и держит
значение в памяти 10 минут (каждый запрос к Oracle 11g поднимает
worker-подпроцесс, а версия меняется раз в релиз). Дальше context processor
`inject_app_version` в `app.py` отдаёт её шаблонам, а
`templates/biro26/site_base.html` выводит в подвале.

Если Oracle недоступен, `current()` вернёт пустую строку и подвал просто не
покажет версию — страница из-за этого не сломается.

## Файлы

| Файл | Назначение |
|---|---|
| `sql/biro26/18_tms_webappvers.sql` | DDL для Oracle |
| `sql/biro26/18_tms_webappvers_mysql.sql` | DDL для MySQL |
| `scripts/set_app_version.py` | запись версии в обе базы, `--show`, `--hash` |
| `models/biro26_version.py` | чтение версии для подвала |
| `templates/biro26/site_base.html` | сам подвал |
