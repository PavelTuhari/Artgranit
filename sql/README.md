# SQL-объекты Oracle для дашбордов

Таблицы, представления, триггеры и пакеты для:

- **Табло отправлений** (bus): `BUS_ROUTES`, `BUS_DEPARTURES`, `V_BUS_DEPARTURES_TODAY`, `BUS_PKG`
- **Кредиты — админка и оператор** (cred): `CRED_BANKS`, `CRED_CATEGORIES`, `CRED_BRANDS`, `CRED_PROGRAMS`, `CRED_PROGRAM_CATEGORIES`, `CRED_PROGRAM_EXCLUDED_BRANDS`, `CRED_PRODUCTS`, `CRED_APPLICATIONS`, представления и пакеты `CRED_ADMIN_PKG`, `CRED_OPERATOR_PKG`
- **Настраиваемые отчёты** (cred): `CRED_REPORTS`, `CRED_REPORT_PARAMS`, пакеты `CRED_REPORTS_PKG`, `CRED_REPORT_LOGIC_PKG`
- **Shell — основной список проектов**: `UNA_SHELL_PROJECTS` (slug, name, dashboard_ids и т.д.) — скрипт `13_shell_projects.sql`

## Развёртывание

Из корня проекта:

```bash
# Развернуть объекты (таблицы, вью, триггеры, пакеты, демо-данные)
python deploy_oracle_objects.py

# Сначала удалить объекты, затем развернуть заново
python deploy_oracle_objects.py --drop

# Только показать, что будет выполнено
python deploy_oracle_objects.py --dry-run
```

Используются переменные из `.env`: `DB_USER`, `DB_PASSWORD`, `WALLET_*`, `CONNECT_STRING` (как в приложении).

## Порядок выполнения

1. `00_drop.sql` — удаление объектов (только при `--drop`)
2. `01_bus_tables.sql` — таблицы табло
3. `02_bus_views.sql` — представления
4. `03_bus_triggers.sql` — триггеры
5. `04_bus_package.sql` — пакет `BUS_PKG`
6. `05_cred_tables.sql` — таблицы кредитов
7. `06_cred_views.sql` — представления
8. `07_cred_triggers.sql` — триггеры
9. `08_cred_admin_package.sql` — пакет `CRED_ADMIN_PKG`
10. `09_cred_operator_package.sql` — пакет `CRED_OPERATOR_PKG`
11. `10_demo_data.sql` — тестовые и демонстрационные данные
12. `12_cred_reports.sql` — таблицы отчётов, пакеты `CRED_REPORTS_PKG`, `CRED_REPORT_LOGIC_PKG`, демо-отчёты
13. `13_shell_projects.sql` — таблица `UNA_SHELL_PROJECTS` (основной список проектов shell: slug, name, dashboard_ids), демо-записи (shell, gara, credit, nufarul)

## Демо-данные

- Банки: Maib, Victoriabank, Moldindconbank, Express Credit
- Категории: Холодильники, Стиральные машины, Телевизоры, Смартфоны, Ноутбуки
- Бренды: Samsung, Apple, LG, Beko, ASUS
- 6 кредитных программ, матрица категорий, исключённые бренды
- 8 товаров, 7 маршрутов и рейсов на сегодня, 3 заявки
