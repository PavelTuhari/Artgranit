# SQL-объекты Oracle для дашбордов

Таблицы, представления, триггеры и пакеты для:

- **Табло отправлений** (bus): `BUS_ROUTES`, `BUS_DEPARTURES`, `V_BUS_DEPARTURES_TODAY`, `BUS_PKG`
- **Кредиты — админка и оператор** (cred): `CRED_BANKS`, `CRED_CATEGORIES`, `CRED_BRANDS`, `CRED_PROGRAMS`, `CRED_PROGRAM_CATEGORIES`, `CRED_PROGRAM_EXCLUDED_BRANDS`, `CRED_PRODUCTS`, `CRED_APPLICATIONS`, представления и пакеты `CRED_ADMIN_PKG`, `CRED_OPERATOR_PKG`
- **Настраиваемые отчёты** (cred): `CRED_REPORTS`, `CRED_REPORT_PARAMS`, пакеты `CRED_REPORTS_PKG`, `CRED_REPORT_LOGIC_PKG`
- **Shell — основной список проектов**: `UNA_SHELL_PROJECTS` (slug, name, dashboard_ids и т.д.) — скрипт `13_shell_projects.sql`
- **Colass — каталог и сметчик**: `CLS_*` (8 таблиц, нормы F3/F5, проект/смета) — скрипты `25_colass_tables.sql`, `26_colass_demo_data.sql`
- **Colass CRM — лиды -> контракт**: `CLS_CRM_*` (источники, этапы, лиды, активности, контракты, email intake) — скрипты `27_colass_crm_tables.sql`, `28_colass_crm_demo_data.sql`
- **Colass Contracts — реестр договоров**: `CLS_CONTRACT_*` (мастер договора, emails/phones/routes, позиции из сметы) — скрипты `29_colass_contracts_tables.sql`, `30_colass_contracts_demo_data.sql`
- **Colass Contracts Workflow**: вложения к договору и групповое согласование (`CLS_CONTRACT_ATTACHMENTS`, `CLS_CONTRACT_APPROVALS`, `CLS_CONTRACT_APPROVAL_STEPS`) — скрипты `31_colass_contracts_workflow_tables.sql`, `32_colass_contracts_workflow_demo_data.sql`

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
14. `14_nufarul_tables.sql` — Nufarul: таблицы
15. `15_nufarul_views.sql` — Nufarul: представления
16-18. `16-18_*` — Nufarul: данные услуг, группы, EN-переводы
19. `19_nufarul_photos.sql` — Nufarul: фото
20. `20_digi_tables.sql` — DigiMarketing: таблицы `DIGI_*`
21. `21_digi_views.sql` — DigiMarketing: представления
22. `22_digi_package.sql` — DigiMarketing: PL/SQL пакет
23. `23_digi_demo_data.sql` — DigiMarketing: демо-данные
24. `24_decor_runtime_tables.sql` — DECOR: нормализованные таблицы `DECOR_*`
25. `25_colass_tables.sql` — Colass: 8 таблиц `CLS_*`, 7 sequences/triggers, 3 views, indexes
26. `26_colass_demo_data.sql` — Colass: 404 INSERT (ресурсы F3, работы F5, нормы, проект/смета/разделы)
27. `27_colass_crm_tables.sql` — Colass CRM: 5 таблиц `CLS_CRM_*`, 5 sequences/triggers, 2 views, справочники этапов/источников
28. `28_colass_crm_demo_data.sql` — Colass CRM: демо-лиды и активности
29. `29_colass_contracts_tables.sql` — Colass Contracts: 5 таблиц `CLS_CONTRACT_*`, 5 sequences/triggers, 2 views
30. `30_colass_contracts_demo_data.sql` — Colass Contracts: демо-договор (связь CRM/Estimate), контакты, маршруты, snapshot позиций
31. `31_colass_contracts_workflow_tables.sql` — вложения к договору + workflow согласования, проверки обязательных приложений
32. `32_colass_contracts_workflow_demo_data.sql` — демо-приложения: финансовые условия, сметные условия, общий прайс-лист
35. `35_agro_tables.sql` — AGRO: 36 таблиц `AGRO_*` (склады, товары, закупки, партии, QA, HACCP, продажи, аудит)
36. `36_agro_views.sql` — AGRO: представления
37. `37_agro_triggers.sql` — AGRO: триггеры auto-ID и бизнес-логика
38. `38_agro_demo_data.sql` — AGRO: демо-данные (поставщики, клиенты, товары, закупки)

## Демо-данные

- Банки: Maib, Victoriabank, Moldindconbank, Express Credit
- Категории: Холодильники, Стиральные машины, Телевизоры, Смартфоны, Ноутбуки
- Бренды: Samsung, Apple, LG, Beko, ASUS
- 6 кредитных программ, матрица категорий, исключённые бренды
- 8 товаров, 7 маршрутов и рейсов на сегодня, 3 заявки
