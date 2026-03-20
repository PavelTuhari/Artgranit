# Artgranit OCI -- Developer Guide

Полное руководство разработчика: архитектура проекта, модули, подключение к Oracle ADB, локальный запуск, deploy, миграция из Git и создание новых модулей.

> **HTML-версия**: `docs/DEVELOPER_GUIDE.html` — открывается в браузере, содержит навигационный sidebar и подсветку SQL.

---

## 1. Архитектура проекта

Artgranit OCI — это мультимодульная платформа, построенная вокруг единственного источника истины: Oracle Autonomous Database в облаке. Задача платформы — предоставить набор бизнес-модулей (кредиты, строительные сметы, складской учёт, химчистка и др.), каждый из которых работает в рамках одного веб-приложения, одной базы данных и одного development workflow.

Выбор технологий обусловлен несколькими принципиальными решениями. **Flask** выбран как легковесный фреймворк, который не навязывает ORM и позволяет работать напрямую с Oracle через нативный драйвер `oracledb`. Это критично, потому что Oracle ADB поддерживает PL/SQL-пакеты, представления и триггеры, являющиеся частью бизнес-логики, и ORM вроде SQLAlchemy скорее мешал бы, чем помогал. **Vanilla JS** на фронтенде — сознательный выбор: каждый модуль самодостаточен, нет общего SPA-фреймворка, а значит нет и единой точки отказа при обновлении React/Vue версий. **WebSockets** через Flask-SocketIO используются только для dashboard-метрик, где нужен настоящий real-time — остальные модули работают по классическому HTTP request-response.

Ключевой архитектурный принцип: *все бизнес-данные живут в Oracle, а не в файлах или SQLite*. Это кажется очевидным, но исторически ряд модулей начинали жить в JSON-файлах как «временное решение». Переход на нормализованные Oracle-таблицы произошёл в процессе эволюции проекта, и теперь это зафиксировано как обязательное правило для всех новых модулей (подробнее см. раздел 9 «Запрещённые паттерны»).

### Стек

| Слой         | Технология                                    |
|--------------|-----------------------------------------------|
| Backend      | Python 3.12 + Flask                           |
| Real-time    | Flask-SocketIO (WebSockets, threading)        |
| Database     | Oracle Autonomous Database (OCI) через `oracledb` |
| Auth wallet  | Oracle Wallet (mTLS)                          |
| Frontend     | Vanilla JS + HTML5/CSS3 + Socket.IO client    |
| Deploy       | tar.gz + SSH/SCP (shell scripts)              |

### MVC-структура

Проект следует классическому паттерну MVC, но с одной особенностью: все маршруты определены в одном файле `app.py` (~200 KB). Это не случайность — Flask не навязывает декомпозицию на blueprints, а все маршруты собраны вместе сознательно, чтобы при чтении кода сразу была видна полная карта URL-пространства приложения. Контроллеры, напротив, разнесены по отдельным файлам — каждый модуль имеет свой контроллер, а зачастую и свою модель-хранилище (`*_oracle_store.py`). Таким образом, `app.py` выполняет роль маршрутизатора и точки входа, а бизнес-логика живёт в контроллерах.

```
Artgranit/
├── app.py                      # Точка входа, все маршруты, SocketIO events
├── config.py                   # Конфигурация из .env
├── requirements.txt            # Python зависимости
├── .env                        # Секреты (НЕ в git)
├── .env.example                # Шаблон .env
│
├── controllers/                # Контроллеры (бизнес-логика + API)
│   ├── auth_controller.py
│   ├── dashboard_controller.py
│   ├── sql_controller.py
│   ├── objects_controller.py
│   ├── shell_controller.py
│   ├── credit_controller.py
│   ├── credit_testing_controller.py
│   ├── nufarul_controller.py
│   ├── colass_controller.py
│   ├── digi_marketing_controller.py
│   ├── agro_admin_controller.py
│   ├── agro_field_controller.py
│   ├── agro_qa_controller.py
│   ├── agro_sales_controller.py
│   ├── agro_warehouse_controller.py
│   ├── documentation_controller.py
│   └── combo_scenario_controller.py
│
├── models/                     # Модели данных и Oracle-хранилища
│   ├── database.py             # DatabaseConnection (pool), DatabaseModel (query helper)
│   ├── shell_project.py        # UNA_SHELL_PROJECTS
│   ├── oracle_runtime_store.py # Append-only event log helper
│   ├── decor_oracle_store.py   # DECOR_* нормализованный Oracle store
│   ├── agro_oracle_store.py    # AGRO_* нормализованный Oracle store
│   └── combo_scenario.py       # Сценарии демо
│
├── services/                   # Сервисы
│   ├── credit_logger.py        # CRED_EVENT_LOG writer
│   ├── report_export.py        # Экспорт отчётов (PDF/XLSX)
│   └── scale_emulator.py       # Эмулятор весов (AGRO)
│
├── integrations/               # Внешние API
│   ├── easycredit_client.py    # EasyCredit API client
│   └── iute_client.py          # Iute API client
│
├── templates/                  # Jinja2 HTML шаблоны
├── static/                     # CSS, JS, изображения
├── sql/                        # Oracle DDL, views, triggers, demo data
├── dashboards/                 # JSON-конфиги дашбордов (00-10)
├── docs/                       # Проектная документация
├── scripts/                    # Утилитарные скрипты
├── data/                       # Runtime JSON (settings, NOT primary state)
└── translations/               # i18n (ru, ro, en)
```

---

## 2. Модули

Платформа Artgranit состоит из девяти бизнес-модулей, каждый из которых проектировался для конкретной предметной области. Модули между собой взаимодействуют минимально: общая для них — процедура аутентификации, Shell-оболочка для навигации и единая база данных Oracle. Такая слабая связанность — намеренное архитектурное решение: каждый модуль можно развивать, тестировать и деплоить как логически независимую единицу.

Каждый модуль характеризуется:
- **Oracle-префиксом** — короткое имя (3-5 символов), которым начинаются все объекты БД. Например, `CRED_BANKS`, `AGRO_ITEMS`, `CLS_RESOURCES`.
- **DDL-скриптами** в `sql/` — полное описание схемы данных модуля.
- **Контроллером** — Python-класс с бизнес-логикой, вызываемый из маршрутов `app.py`.
- **HTML-шаблоном** — самостоятельная страница (не SPA-компонент, а полноценная страница).
- **API-маршрутами** под `/api/<module>/*` — JSON REST API для AJAX-запросов из фронтенда.

### 2.1 Shell (проектная оболочка)

| Параметр       | Значение                                |
|----------------|----------------------------------------|
| Префикс Oracle | `UNA_SHELL_*`                           |
| Таблицы        | `UNA_SHELL_PROJECTS`                   |
| DDL            | `sql/13_shell_projects.sql`            |
| Контроллер     | `controllers/shell_controller.py`      |
| Модель         | `models/shell_project.py`              |
| Шаблоны        | `shell_projects.html`, `shell_dashboard_mdi.html` |
| UI URL         | `/UNA.md/orasldev/` (main MDI)        |

Shell -- корневая оболочка приложения. Хранит список проектов (slug, name, dashboard_ids) в нормализованной таблице `UNA_SHELL_PROJECTS`. Каждый проект ведёт на свой набор дашбордов.

Shell можно воспринимать как «рабочий стол» всей платформы. Когда пользователь заходит на `/UNA.md/orasldev/`, он попадает в MDI-интерфейс (Multiple Document Interface) -- среду с плавающими окнами, аналогичную Oracle SQL Developer. Оттуда открываются SQL-воркшиты, браузер объектов, дашборды. Shell -- это именно оболочка, в которую встроены все остальные модули.

Таблица `UNA_SHELL_PROJECTS` играет роль реестра проектов. Каждый проект -- это запись с `slug` (уникальный URL-идентификатор), `name`, `description` и строкой `dashboard_ids` (список ID дашбордов через запятую). Когда добавляется новый модуль, он регистрируется в этой таблице, чтобы появиться в навигации Shell. Это аналог `TForm` с `TMainMenu` в Delphi/C++ Builder: Shell -- главная форма, а модули -- дочерние формы, вызываемые через меню.

### 2.2 Dashboard (мониторинг Oracle)

| Параметр       | Значение                              |
|----------------|--------------------------------------|
| Контроллер     | `controllers/dashboard_controller.py` |
| Шаблоны        | `dashboard_mdi.html`, `dashboard.html` |
| Конфиги        | `dashboards/dashboard_00.json` - `dashboard_10.json` |
| UI URL         | `/UNA.md/orasldev/dashboard`, `/UNA.md/orasldev/dashboard/<id>` |

Real-time метрики Oracle: CPU, RAM, Sessions, Top SQL, Tablespaces. WebSocket-обновления каждые 60 сек. Fullscreen-режим для отдельных панелей.

Dashboard -- это панель мониторинга Oracle, аналогичная тому, что вы видели бы в Oracle Enterprise Manager, но встроенная прямо в приложение. Дашборд конфигурируется через JSON-файлы (`dashboards/dashboard_00.json` -- `dashboard_10.json`), каждый из которых описывает набор виджетов: какой SQL-запрос выполняется, как часто обновляются данные, в каком виде отображаются (карточка, таблица, график). WebSocket-соединение инициируется при открытии дашборда, и далее сервер каждые 60 секунд отправляет обновлённые метрики без повторных HTTP-запросов. Это особенно важно для метрики Top SQL: запрос к `v$sqlarea` может быть ресурсоёмким, и контроллер использует упрощённую выборку без тяжёлого поля `sql_text`, чтобы не перегружать ADB.

### 2.3 BUS (табло отправлений, автовокзал)

| Параметр       | Значение                                 |
|----------------|------------------------------------------|
| Префикс Oracle | `BUS_*`                                   |
| Таблицы        | `BUS_ROUTES`, `BUS_DEPARTURES`           |
| Представления  | `V_BUS_DEPARTURES_TODAY`                 |
| Пакеты         | `BUS_PKG`                                |
| DDL            | `sql/01-04_bus_*.sql`                    |

BUS -- модуль табло отправлений автовокзала. Это самый компактный модуль в платформе и, по сути, первый, с которого началась разработка Artgranit. Модуль демонстрирует базовый паттерн: нормализованная Oracle-схема (маршруты + рейсы), представление для фильтрации «сегодняшних» отправлений, PL/SQL-пакет `BUS_PKG` для бизнес-операций, триггеры для автогенерации ID. Если вы хотите понять, как устроен «минимальный модуль» Artgranit -- начните с BUS.

### 2.4 CRED (кредиты -- Bomba, EasyCredit, Iute)

| Параметр       | Значение                                                      |
|----------------|---------------------------------------------------------------|
| Префикс Oracle | `CRED_*`                                                      |
| Таблицы        | `CRED_BANKS`, `CRED_CATEGORIES`, `CRED_BRANDS`, `CRED_PROGRAMS`, `CRED_PROGRAM_CATEGORIES`, `CRED_PROGRAM_EXCLUDED_BRANDS`, `CRED_PRODUCTS`, `CRED_APPLICATIONS`, `CRED_EVENT_LOG`, `CRED_REPORTS`, `CRED_REPORT_PARAMS` |
| Пакеты         | `CRED_ADMIN_PKG`, `CRED_OPERATOR_PKG`, `CRED_REPORTS_PKG`, `CRED_REPORT_LOGIC_PKG` |
| DDL            | `sql/05-12_cred_*.sql`                                        |
| Контроллер     | `controllers/credit_controller.py`                            |
| Интеграции     | `integrations/easycredit_client.py`, `integrations/iute_client.py` |
| UI URL         | `/UNA.md/orasldev/credit-admin`, `/UNA.md/orasldev/credit-operator`, `/UNA.md/orasldev/credit-portfolio-bomba`, `/UNA.md/orasldev/credit-easycredit`, `/UNA.md/orasldev/credit-iute` |

Логирование кредитных операций -- append-only `CRED_EVENT_LOG`, не generic KV.

Кредитный модуль -- один из самых развитых в платформе. Он обслуживает полный цикл оформления потребительского кредита в рознице: администратор настраивает банки, категории товаров и кредитные программы (с матрицей «программа-категория» и списком исключённых брендов), а оператор в торговом зале оформляет заявку на конкретный товар. Интеграции с внешними кредитными API (EasyCredit и Iute) реализованы как отдельные клиенты в `integrations/` и позволяют отправлять заявки, проверять статусы и получать решения в реальном времени.

Важная деталь: журнал событий кредитного модуля хранится в `CRED_EVENT_LOG` -- это *append-only* лог (данные только добавляются, никогда не перезаписываются). Такая архитектура была принята после того, как ранние версии пытались использовать generic-таблицу `APP_EVENT_LOG` для всех модулей, что приводило к путанице и невозможности построить нормальные отчёты. Сейчас каждый модуль, которому нужен event log, обязан создавать свой собственный.

PL/SQL-пакеты `CRED_ADMIN_PKG` и `CRED_OPERATOR_PKG` инкапсулируют серверную логику: администратор вызывает процедуры пакета админки, оператор -- свои. Пакеты `CRED_REPORTS_PKG` и `CRED_REPORT_LOGIC_PKG` отвечают за настраиваемые отчёты, где администратор определяет SQL-запрос, параметры и формат вывода.

### 2.5 NUF (Nufarul -- химчистка/прачечная)

| Параметр       | Значение                                            |
|----------------|-----------------------------------------------------|
| Префикс Oracle | `NUF_*`                                              |
| DDL            | `sql/14-22_nufarul_*.sql`                            |
| Контроллер     | `controllers/nufarul_controller.py`                  |
| Шаблоны        | `nufarul_admin.html`, `nufarul_operator.html`, `nufarul/document_*.html` |
| UI URL         | `/UNA.md/orasldev/nufarul-admin`, `/UNA.md/orasldev/nufarul-operator` |

Услуги по группам (RU/RO/EN), заказы, статусы, штрих-коды, первичные документы (Bon de Comanda, Comanda, Jurnal Registru). Vector search, blockchain orders, фото.

Nufarul -- модуль для реальной химчистки/прачечной, где бизнес-процесс выглядит так: клиент приносит вещи, оператор регистрирует заказ (выбирая услуги из каталога), присваивает штрих-код, печатает квитанцию. Далее заказ проходит по статусам (принят -> в работе -> готов -> выдан). Именно поэтому в Nufarul есть отдельный UI для администратора (управление услугами и тарифами) и для оператора (приём/выдача в зале).

Особенность Nufarul -- трёхъязычный каталог услуг (RU/RO/EN). Каждая услуга хранится с переводами, и интерфейс переключается между языками через Flask-Babel. Первичные документы (Bon de Comanda, Comanda, Jurnal Registru) -- это HTML-шаблоны в подкаталоге `templates/nufarul/`, которые генерируются из данных заказа и предназначены для печати на обычном принтере прямо из браузера.

Продвинутые функции -- vector search (поиск услуг по семантическому сходству, использует Oracle AI Vector Search), blockchain-заказы (хэширование для гарантии неизменности) и фото-галерея -- реализованы как отдельные SQL-скрипты, которые выполняются вручную при необходимости (не включены в основной deploy).

### 2.6 DIGI (DigiMarketing -- социальные медиа)

| Параметр       | Значение                                       |
|----------------|------------------------------------------------|
| Префикс Oracle | `DIGI_*`                                        |
| DDL            | `sql/20-23_digi_*.sql`                          |
| Контроллер     | `controllers/digi_marketing_controller.py`      |
| Шаблоны        | `digi_marketing.html`                           |
| UI URL         | `/UNA.md/orasldev/digi-marketing`, `/UNA.md/orasldev/digi-sm` |

DigiMarketing -- модуль управления маркетинговыми кампаниями в социальных медиа. Цель модуля -- дать маркетологу инструмент для планирования, создания и аналитики контента для социальных сетей. Данные хранятся в таблицах с префиксом `DIGI_*`, бизнес-логика вынесена в PL/SQL-пакет. Контроллер (`digi_marketing_controller.py`, ~57 KB) достаточно объёмный, поскольку покрывает полный CRUD цикл кампаний, постов, расписаний и аналитики.

### 2.7 DECOR (алюминиевые фасадные системы)

| Параметр       | Значение                                                 |
|----------------|----------------------------------------------------------|
| Префикс Oracle | `DECOR_*`                                                 |
| Таблицы        | `DECOR_MATERIALS`, `DECOR_STATUSES`, `DECOR_SETTINGS`, `DECOR_ORDERS`, `DECOR_ORDER_ITEMS`, `DECOR_SLIDING_*` и др. |
| DDL            | `sql/19_decor_shell_project.sql`, `sql/24_decor_runtime_tables.sql` |
| Контроллер     | inline в `app.py` + API через `decor_oracle_store`         |
| Модель         | `models/decor_oracle_store.py`                           |
| Шаблоны        | `decor_admin.html`, `decor_operator.html`               |
| UI URL         | `/UNA.md/orasldev/decor-admin`, `/UNA.md/orasldev/decor`, `/UNA.md/orasldev/decor-operator` |

Эталонный модуль нормализованного Oracle-хранения. Материалы, настройки, заказы + позиции, раздвижные системы -- всё в отдельных таблицах.

DECOR занимает особое место в архитектуре Artgranit. Это *эталонный модуль*, на который нужно ориентироваться при создании новых модулей. Именно здесь впервые была реализована полная нормализованная Oracle-схема взамен ранее существовавшего JSON-хранилища.

Бизнес-домен DECOR -- алюминиевые фасадные и раздвижные системы. Оператор собирает заказ из материалов (профили, стекло, фурнитура), система рассчитывает стоимость с учётом курса валюты, наценки, процента отходов. Все справочные данные -- материалы, статусы, настройки расчёта -- хранятся в отдельных таблицах, а не в одном JSON-поле. Заказы разделены на документ-шапку (`DECOR_ORDERS`) и строки (`DECOR_ORDER_ITEMS`) -- классический паттерн «master-detail», хорошо знакомый каждому, кто работал с учётными системами.

Модель данных реализована в `models/decor_oracle_store.py` (55 KB) -- это единый класс, который предоставляет CRUD-методы для всех таблиц `DECOR_*`. Публичный API возвращает nested dict для удобства фронтенда, но persistence под ним строго нормализована. Если вам нужно понять, как строить Oracle store для нового модуля -- начните с чтения `decor_oracle_store.py`.

### 2.8 CLS (Colass -- строительная сметная система)

| Параметр       | Значение                                                     |
|----------------|--------------------------------------------------------------|
| Префикс Oracle | `CLS_*`, `CLS_CRM_*`, `CLS_CONTRACT_*`                      |
| Таблицы        | `CLS_RESOURCE_TYPES`, `CLS_RESOURCES`, `CLS_WORK_CATALOG`, `CLS_WORK_RESOURCES`, `CLS_PROJECTS`, `CLS_ESTIMATES`, `CLS_ESTIMATE_SECTIONS`, `CLS_ESTIMATE_ITEMS` |
| CRM таблицы    | `CLS_CRM_SOURCES`, `CLS_CRM_STAGES`, `CLS_CRM_LEADS`, `CLS_CRM_ACTIVITIES`, `CLS_CRM_EMAIL_INTAKE` |
| Contracts      | `CLS_CONTRACT_MASTER`, `CLS_CONTRACT_EMAILS`, `CLS_CONTRACT_PHONES`, `CLS_CONTRACT_ROUTES`, `CLS_CONTRACT_ITEMS`, `CLS_CONTRACT_ATTACHMENTS`, `CLS_CONTRACT_APPROVALS`, `CLS_CONTRACT_APPROVAL_STEPS` |
| DDL            | `sql/25-32_colass_*.sql`                                     |
| Контроллер     | `controllers/colass_controller.py` (114 KB)                  |
| Шаблоны        | `colass_catalog.html`, `colass_estimator.html`, `colass_crm.html`, `colass_contracts.html` |
| UI URL         | `/UNA.md/orasldev/colass-catalog`, `/UNA.md/orasldev/colass-estimator`, `/UNA.md/orasldev/colass-crm`, `/UNA.md/orasldev/colass-contracts` |
| API prefix     | `/api/colass/*`                                              |

Каталог работ (F5), ресурсы (F3), нормы. Сметчик: проекты, сметы, разделы, позиции. CRM: лиды, воронка, активности. Договоры: реестр, вложения, workflow согласования.

Colass -- строительная сметная система, и это самый крупный модуль по объёму кода (контроллер 114 KB). Домен разделён на три связанных подсистемы, каждая со своим набором таблиц:

**Каталог** (`CLS_*`) -- база нормативных данных: типы ресурсов, ресурсы с ценами и единицами измерения (из документов F3), каталог работ (из F5), нормы расхода ресурсов на единицу работы. Сметчик позволяет создать проект, внутри него сметы, разделить смету на разделы и добавлять позиции из каталога. При добавлении позиции система автоматически подтягивает нормы и рассчитывает стоимость.

**CRM** (`CLS_CRM_*`) -- управление лидами: от первого контакта (источник, этап воронки) до активностей (звонки, встречи, письма). Email intake позволяет автоматически создавать лиды из входящих писем. Таблицы CRM спроектированы независимо от сметного каталога -- связь между ними возникает только на уровне договора.

**Contracts** (`CLS_CONTRACT_*`) -- реестр договоров, который связывает CRM-лида с конкретной сметой. Договор хранит контактную информацию (emails, phones, routes = адреса доставки), снэпшот позиций из сметы на момент подписания, вложения и workflow многоуровнего согласования (цепочка `CLS_CONTRACT_APPROVALS` -> `CLS_CONTRACT_APPROVAL_STEPS`).

Обратите внимание на использование трёх подпрефиксов: `CLS_`, `CLS_CRM_`, `CLS_CONTRACT_`. Это допустимый паттерн, когда модуль содержит несколько самостоятельных предметных подобластей. Альтернатива -- разделить на три отдельных модуля -- была отвергнута, т.к. все три подсистемы тесно связаны бизнес-процессом «лид -> смета -> договор».

### 2.9 AGRO (фрукты/овощи -- складской учёт)

| Параметр       | Значение                                              |
|----------------|-------------------------------------------------------|
| Префикс Oracle | `AGRO_*`                                               |
| Таблицы (36)   | `AGRO_SUPPLIERS`, `AGRO_CUSTOMERS`, `AGRO_WAREHOUSES`, `AGRO_ITEMS`, `AGRO_PURCHASE_DOCS`, `AGRO_PURCHASE_LINES`, `AGRO_BATCHES`, `AGRO_SALES_DOCS`, `AGRO_SALES_LINES`, `AGRO_QA_*`, `AGRO_HACCP_*` и др. |
| DDL            | `sql/35-38_agro_*.sql`                                 |
| Контроллеры    | `agro_admin_controller.py`, `agro_field_controller.py`, `agro_qa_controller.py`, `agro_sales_controller.py`, `agro_warehouse_controller.py` |
| Модель         | `models/agro_oracle_store.py` (141 KB)                 |
| Шаблоны        | `agro_mdi.html`, `agro_admin.html`, `agro_field.html`, `agro_warehouse.html`, `agro_qa.html`, `agro_sales.html` |
| UI URL         | `/UNA.md/orasldev/agro`, `/UNA.md/orasldev/agro-admin`, `/UNA.md/orasldev/agro-field`, `/UNA.md/orasldev/agro-warehouse`, `/UNA.md/orasldev/agro-qa`, `/UNA.md/orasldev/agro-sales` |
| API prefix     | `/api/agro/*`                                          |

Поставщики, клиенты, склады, ячейки хранения, товары, упаковки, транспорт, валюты, штрих-коды, закупки, партии, движение товара, QA-чеклисты, HACCP, продажи, экспорт, аудит-лог.

AGRO -- самый масштабный модуль по количеству Oracle-объектов (36 таблиц, 36 sequences). Он моделирует полный цикл работы фруктово-овощного склада: от закупки партии у поставщика до продажи клиенту с промежуточными этапами хранения, контроля качества и переработки.

Архитектурно AGRO разделён на пять контроллеров по ролям пользователей: **admin** (справочники: товары, поставщики, клиенты, валюты, формулы ценообразования), **field** (приёмка товара на складе с подключением весов -- см. `services/scale_emulator.py`), **warehouse** (движение товара по ячейкам хранения, температурный мониторинг), **qa** (чек-листы качества, HACCP-планы, критические контрольные точки), **sales** (формирование документов продажи, экспортные декларации). Такое разделение контроллеров по ролям -- хорошая практика для крупного модуля, потому что иначе один контроллер вырос бы до неуправляемых размеров.

Модель данных (`models/agro_oracle_store.py`, 141 KB) -- самая объёмная в проекте. Она реализует CRUD для всех 36 таблиц и содержит бизнес-логику: расчёт стоимости партии, движение товара (приход/расход/перемещение между ячейками), формулы ценообразования с учётом курсов валют. Аудит-лог (`AGRO_AUDIT_LOG`) фиксирует каждое изменение сущностей для полной трассируемости -- это требование пищевой безопасности, которое пронизывает весь модуль.

---

## 3. Подключение к Oracle ADB (APEX / ADB -- единый аккаунт)

Все модули подключаются к **одной базе данных Oracle Autonomous Database** (OCI), используя **один аккаунт ADMIN**. Подключение через Oracle Wallet (mTLS).

### 3.1 Инфраструктура Oracle Cloud (OCI)

```
Oracle Cloud Account
└── Autonomous Database (ADB-S)
    ├── Name:     HXPAVUNKCLU9HE7Q
    ├── Region:   eu-frankfurt-1
    ├── Type:     Shared (ADB-S)
    ├── User:     ADMIN
    └── APEX:     доступен через tот же ADB (https://...adb.eu-frankfurt-1.oraclecloud.com/ords/...)
```

APEX и ADB -- это один и тот же сервис: APEX работает внутри ADB, подключаться отдельно не нужно. APEX Workspaces создаются администратором внутри той же БД.

### 3.2 Структура подключения

```
Приложение (Python / oracledb)
    │
    ├── .env                        # DB_USER, DB_PASSWORD, WALLET_*, CONNECT_STRING
    │
    ├── Oracle Wallet (папка)       # Скачивается из OCI Console один раз
    │   ├── tnsnames.ora
    │   ├── sqlnet.ora
    │   ├── cwallet.sso
    │   ├── ewallet.p12
    │   ├── ewallet.pem
    │   ├── keystore.jks
    │   └── truststore.jks
    │
    └── oracledb.connect(
          user     = DB_USER,       # ADMIN
          password = DB_PASSWORD,
          dsn      = CONNECT_STRING,  # полный TNS descriptor
          wallet_location = WALLET_DIR,
          wallet_password = WALLET_PASSWORD
        )
```

### 3.3 Переменные .env для Oracle

```bash
# Пользователь БД
DB_USER=ADMIN

# Пароль БД (НЕ коммить!)
DB_PASSWORD=<your_password>

# Пароль Oracle wallet (НЕ коммить!)
WALLET_PASSWORD=<your_wallet_password>

# Путь к распакованной папке wallet
# Локально:   WALLET_DIR=wallet_HXPAVUNKCLU9HE7Q             (относительный)
# На remote:  WALLET_DIR=/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q  (абсолютный!)
WALLET_DIR=wallet_HXPAVUNKCLU9HE7Q

# TNS alias (опционально)
TNS_ALIAS=hxpavunkclu9he7q_high

# Полный TNS connect string (ОБЯЗАТЕЛЬНО)
CONNECT_STRING=(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))(connect_data=(service_name=g47056ff8b1b3d4_hxpavunkclu9he7q_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))
```

### 3.4 Как скачать Oracle Wallet

1. Войти на https://cloud.oracle.com
2. Перейти: **Oracle Database** -> **Autonomous Database** -> выбрать БД
3. Нажать **DB Connection** -> **Download Wallet**
4. Задать пароль для wallet (это `WALLET_PASSWORD`)
5. Распаковать ZIP в папку
6. Указать путь в `WALLET_DIR`

### 3.5 Где живёт wallet

| Окружение | Путь wallet                                              |
|-----------|----------------------------------------------------------|
| Локально  | `./wallet_HXPAVUNKCLU9HE7Q/` (в корне проекта, в .gitignore) |
| Remote    | `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`   |

Wallet **не включается в Git** (правило `.gitignore`: `wallet_*/`, `Wallet_*.zip`). На remote wallet хранится вне каталога деплоя, чтобы `deploy_to_remote.sh` не мог его потерять.

---

## 4. Миграция проекта из Git (с нуля)

### 4.1 Предварительные требования

- Python 3.12+ (macOS: `brew install python@3.12`, Ubuntu: `apt install python3.12`)
- Git
- Oracle Wallet ZIP (получить у администратора OCI или скачать из OCI Console)
- Доступ к аккаунту Oracle Cloud (один общий аккаунт)

### 4.2 Шаги миграции

```bash
# 1. Клонируем репозиторий
git clone https://github.com/<org>/Artgranit.git
cd Artgranit

# 2. Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Устанавливаем зависимости
pip install -r requirements.txt

# 4. Настраиваем .env
cp .env.example .env
# Редактируем .env: вписываем реальные DB_PASSWORD, WALLET_PASSWORD
# Для полного списка переменных см. раздел 3.3

# 5. Распаковываем Oracle Wallet
#    Получите Wallet_HXPAVUNKCLU9HE7Q.zip у администратора
unzip Wallet_HXPAVUNKCLU9HE7Q.zip -d wallet_HXPAVUNKCLU9HE7Q
#    Убедитесь, что WALLET_DIR в .env указывает на эту папку

# 6. Разворачиваем Oracle-объекты (таблицы, вью, триггеры, пакеты, демо-данные)
python deploy_oracle_objects.py
#    Первый раз: создаёт все таблицы и загружает демо-данные
#    Для полного пересоздания: python deploy_oracle_objects.py --drop

# 7. Запускаем приложение
./run_local.sh
#    Или вручную:
#    export ENVIRONMENT=LOCAL PORT=3003 SERVER_HOST=0.0.0.0
#    python app.py
```

### 4.3 Проверка после запуска

| Что проверить                 | URL                                                    |
|-------------------------------|-------------------------------------------------------|
| Логин                         | http://localhost:3003/login                            |
| SQL Worksheet (shell)         | http://localhost:3003/UNA.md/orasldev/                |
| Dashboard                     | http://localhost:3003/UNA.md/orasldev/dashboard       |
| Кредиты (админ)               | http://localhost:3003/UNA.md/orasldev/credit-admin    |
| Nufarul (оператор)            | http://localhost:3003/UNA.md/orasldev/nufarul-operator|
| DECOR (оператор)              | http://localhost:3003/UNA.md/orasldev/decor-operator  |
| Colass (каталог)              | http://localhost:3003/UNA.md/orasldev/colass-catalog  |
| Colass (сметчик)              | http://localhost:3003/UNA.md/orasldev/colass-estimator|
| Colass (CRM)                  | http://localhost:3003/UNA.md/orasldev/colass-crm      |
| Colass (договоры)             | http://localhost:3003/UNA.md/orasldev/colass-contracts |
| AGRO (мульти-tab)             | http://localhost:3003/UNA.md/orasldev/agro            |
| Документация                  | http://localhost:3003/UNA.md/orasldev/docs            |
| Тест-страница                 | http://localhost:3003/test.html                       |

---

## 5. Oracle DDL -- полный скрипт БД

Все SQL-скрипты для создания объектов Oracle находятся в `sql/` и **отслеживаются в Git**.

### 5.1 Порядок выполнения скриптов

| #   | Файл                                     | Модуль   | Что создаёт                                           |
|-----|------------------------------------------|----------|-------------------------------------------------------|
| 00  | `00_drop.sql`                            | (все)    | DROP всех объектов (только при `--drop`)              |
| 01  | `01_bus_tables.sql`                      | BUS      | `BUS_ROUTES`, `BUS_DEPARTURES`                        |
| 02  | `02_bus_views.sql`                       | BUS      | `V_BUS_DEPARTURES_TODAY`                              |
| 03  | `03_bus_triggers.sql`                    | BUS      | Триггеры auto-ID                                     |
| 04  | `04_bus_package.sql`                     | BUS      | `BUS_PKG`                                             |
| 05  | `05_cred_tables.sql`                     | CRED     | Банки, категории, бренды, программы, заявки           |
| 06  | `06_cred_views.sql`                      | CRED     | Представления                                        |
| 07  | `07_cred_triggers.sql`                   | CRED     | Триггеры                                             |
| 08  | `08_cred_admin_package.sql`              | CRED     | `CRED_ADMIN_PKG`                                      |
| 09  | `09_cred_operator_package.sql`           | CRED     | `CRED_OPERATOR_PKG`                                   |
| 10  | `10_demo_data.sql`                       | BUS+CRED | Демо-данные (банки, маршруты, рейсы, товары)         |
| 11  | `11_cred_program_products.sql`           | CRED     | Привязка продуктов к программам                       |
| 12  | `12_cred_reports.sql`                    | CRED     | Отчёты, `CRED_REPORTS_PKG`, `CRED_REPORT_LOGIC_PKG`  |
| 13  | `13_shell_projects.sql`                  | SHELL    | `UNA_SHELL_PROJECTS` + демо-проекты                   |
| 14  | `14_nufarul_tables.sql`                  | NUF      | Таблицы Nufarul                                       |
| 15  | `15_nufarul_views.sql`                   | NUF      | Представления Nufarul                                 |
| 19  | `19_decor_shell_project.sql`             | DECOR    | INSERT проекта DECOR в shell                          |
| 20  | `20_digi_tables.sql`                     | DIGI     | Таблицы DigiMarketing                                 |
| 21  | `21_digi_views.sql`                      | DIGI     | Представления DigiMarketing                           |
| 22  | `22_digi_package.sql`                    | DIGI     | Пакет DigiMarketing                                   |
| 23  | `23_digi_demo_data.sql`                  | DIGI     | Демо-данные DigiMarketing                             |
| 24  | `24_decor_runtime_tables.sql`            | DECOR    | `DECOR_MATERIALS`, `DECOR_ORDERS`, `DECOR_SETTINGS` и др. |
| 25  | `25_colass_tables.sql`                   | CLS      | 8 таблиц `CLS_*` (ресурсы, работы, нормы, проекты, сметы) |
| 26  | `26_colass_demo_data.sql`                | CLS      | 404 INSERT (ресурсы F3, работы F5, нормы)            |
| 27  | `27_colass_crm_tables.sql`              | CLS      | 5 таблиц `CLS_CRM_*` (лиды, этапы, источники)       |
| 28  | `28_colass_crm_demo_data.sql`           | CLS      | Демо-лиды и активности                               |
| 29  | `29_colass_contracts_tables.sql`        | CLS      | 5 таблиц `CLS_CONTRACT_*`                            |
| 30  | `30_colass_contracts_demo_data.sql`     | CLS      | Демо-договор CRM/Estimate                            |
| 31  | `31_colass_contracts_workflow_tables.sql`| CLS      | Вложения + workflow согласования                     |
| 32  | `32_colass_contracts_workflow_demo_data.sql`| CLS   | Демо-приложения к договору                            |
| 35  | `35_agro_tables.sql`                     | AGRO     | 36 таблиц `AGRO_*`                                    |
| 36  | `36_agro_views.sql`                      | AGRO     | Представления AGRO                                    |
| 37  | `37_agro_triggers.sql`                   | AGRO     | Триггеры AGRO                                        |
| 38  | `38_agro_demo_data.sql`                  | AGRO     | Демо-данные AGRO                                      |

Дополнительные скрипты (не включены в `deploy_oracle_objects.py`, выполняются вручную при необходимости):

| Файл                                | Назначение                              |
|--------------------------------------|-----------------------------------------|
| `13_shell_projects_fix_gara.sql`     | Фикс проекта gara                       |
| `16_nufarul_services_data.sql`       | Данные услуг Nufarul                    |
| `17_nufarul_service_groups.sql`      | Группы услуг                            |
| `18_nufarul_name_en.sql`             | Английские имена                        |
| `19_nufarul_photos.sql`              | Фото Nufarul                            |
| `20_nufarul_ro_translations.sql`     | Румынские переводы                      |
| `21_nufarul_vector_search.sql`       | Vector search Nufarul                   |
| `22_nufarul_blockchain_orders.sql`   | Blockchain-заказы Nufarul               |

### 5.2 Команды deploy Oracle-объектов

```bash
# Развернуть все объекты (без удаления существующих)
python deploy_oracle_objects.py

# Полное пересоздание (DROP + CREATE)
python deploy_oracle_objects.py --drop

# Только показать, что будет выполнено (dry-run)
python deploy_oracle_objects.py --dry-run
```

### 5.3 Безопасность: что НЕ в Git

| Файл/папка                  | В .gitignore | Почему                                |
|-----------------------------|-------------|---------------------------------------|
| `.env`                      | Да         | Содержит DB_PASSWORD, WALLET_PASSWORD  |
| `wallet_*/`                 | Да         | Oracle Wallet с PEM/JKS ключами       |
| `Wallet_*.zip`              | Да         | Архив wallet                           |
| `oracle_connections.json`   | Да         | Пароли подключений                     |
| `data/easycredit_settings.json` | Да     | API пароли EasyCredit                  |
| `data/iute_settings.json`   | Да         | API ключ Iute                          |
| `data/credit_log.jsonl`     | Да         | Может содержать PII                    |

---

## 6. Deploy на remote сервер

### 6.1 Кодовый deploy

```bash
# С локальной машины:
./deploy_to_remote.sh
```

Что делает скрипт:
1. Создаёт backup текущего remote-проекта
2. Архивирует локальный проект (исключая `.env`, `wallet_*`, `venv/`, `__pycache__/`)
3. Копирует архив на remote через SCP
4. Сохраняет remote `.env` и relative wallet (если есть)
5. Распаковывает новый код
6. Восстанавливает `.env` и wallet
7. Устанавливает зависимости (`pip install -r requirements.txt`)
8. Перезапускает `app.py`

### 6.2 Deploy Oracle DDL (отдельный шаг)

```bash
# Локально (для общей ADB -- БД одна на все окружения):
python deploy_oracle_objects.py

# На remote при необходимости:
DEPLOY_ORACLE_ON_REMOTE=1 ./deploy_to_remote.sh
```

### 6.3 Remote-сервер

| Параметр     | Значение                                           |
|--------------|---------------------------------------------------|
| Host         | `92.5.3.187`                                       |
| Port         | `8000`                                             |
| Path         | `/home/ubuntu/artgranit`                           |
| Wallet       | `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q` |
| Python venv  | `/home/ubuntu/artgranit/venv`                      |
| Logs         | `/home/ubuntu/artgranit/app.log`                   |
| URL          | `http://92.5.3.187:8000/login`                     |

---

## 7. Локальный запуск

### Быстрый старт (macOS)

```bash
cd /Users/pt/Projects.AI/Artgranit
./run_local.sh
```

`run_local.sh` автоматически:
- создаёт `venv` если нет
- активирует его
- устанавливает зависимости если нужно
- задаёт `ENVIRONMENT=LOCAL`, `PORT=3003`
- запускает `python app.py`

### Ручной запуск

```bash
cd /Users/pt/Projects.AI/Artgranit
source venv/bin/activate
export ENVIRONMENT=LOCAL PORT=3003 SERVER_HOST=0.0.0.0
python app.py
```

### Порты

| Окружение | Порт |
|-----------|------|
| LOCAL     | 3003 |
| REMOTE    | 8000 |

---

## 8. How to Create a New Module

Пошаговая инструкция для создания нового модуля (для разработчика или AI-агента).

### 8.1 Выбрать префикс

Выбрать короткий (3-5 символов) уникальный префикс. Все Oracle-объекты модуля именуются `PREFIX_*`.

Занятые префиксы: `BUS_`, `CRED_`, `NUF_`, `UNA_SHELL_`, `DIGI_`, `DECOR_`, `CLS_`, `CLS_CRM_`, `CLS_CONTRACT_`, `AGRO_`.

Пример для нового модуля "Логистика": `LOG_` или `LOGIS_`.

### 8.2 Создать Oracle DDL

Создать SQL-файл в `sql/` с номером, продолжающим нумерацию:

```bash
sql/40_logis_tables.sql        # Таблицы и sequences
sql/41_logis_views.sql         # Представления
sql/42_logis_triggers.sql      # Триггеры
sql/43_logis_demo_data.sql     # Демо-данные
```

Шаблон `sql/40_logis_tables.sql`:

```sql
-- ============================================================
-- LOGIS module (LOGIS_*) — logistics management
-- Tables: N
-- Sequences: N
-- ============================================================

-- Sequences
CREATE SEQUENCE LOGIS_ORDERS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE LOGIS_ORDER_ITEMS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- Master data
CREATE TABLE LOGIS_WAREHOUSES (
  ID             NUMBER         NOT NULL,
  CODE           VARCHAR2(30)   NOT NULL,
  NAME           VARCHAR2(200)  NOT NULL,
  IS_ACTIVE      CHAR(1)        DEFAULT 'Y' NOT NULL,
  CREATED_AT     TIMESTAMP      DEFAULT CURRENT_TIMESTAMP NOT NULL,
  UPDATED_AT     TIMESTAMP      DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT PK_LOGIS_WAREHOUSES PRIMARY KEY (ID),
  CONSTRAINT UK_LOGIS_WAREHOUSES_CODE UNIQUE (CODE),
  CONSTRAINT CHK_LOGIS_WAREHOUSES_ACT CHECK (IS_ACTIVE IN ('Y','N'))
);
/

-- Auto-ID trigger
CREATE OR REPLACE TRIGGER LOGIS_WAREHOUSES_BI
BEFORE INSERT ON LOGIS_WAREHOUSES FOR EACH ROW
WHEN (NEW.ID IS NULL) BEGIN :NEW.ID := LOGIS_ORDERS_SEQ.NEXTVAL; END;
/

-- Documents
CREATE TABLE LOGIS_ORDERS (
  ID             NUMBER         NOT NULL,
  ORDER_NO       VARCHAR2(30)   NOT NULL,
  WAREHOUSE_ID   NUMBER         NOT NULL,
  STATUS         VARCHAR2(30)   DEFAULT 'DRAFT',
  TOTAL_AMOUNT   NUMBER(18,2)   DEFAULT 0,
  CREATED_AT     TIMESTAMP      DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT PK_LOGIS_ORDERS PRIMARY KEY (ID),
  CONSTRAINT FK_LOGIS_ORDERS_WH FOREIGN KEY (WAREHOUSE_ID) REFERENCES LOGIS_WAREHOUSES(ID)
);
/

-- Document items
CREATE TABLE LOGIS_ORDER_ITEMS (
  ID             NUMBER         NOT NULL,
  ORDER_ID       NUMBER         NOT NULL,
  ITEM_NAME      VARCHAR2(500)  NOT NULL,
  QTY            NUMBER(18,4)   DEFAULT 1,
  PRICE          NUMBER(18,4)   DEFAULT 0,
  AMOUNT         NUMBER(18,4)   DEFAULT 0,
  CONSTRAINT PK_LOGIS_ORDER_ITEMS PRIMARY KEY (ID),
  CONSTRAINT FK_LOGIS_ORDER_ITEMS_ORD FOREIGN KEY (ORDER_ID) REFERENCES LOGIS_ORDERS(ID)
);
/

-- Event log (append-only)
CREATE TABLE LOGIS_EVENT_LOG (
  ID             NUMBER         NOT NULL,
  EVENT_TYPE     VARCHAR2(60)   NOT NULL,
  ENTITY_TYPE    VARCHAR2(60),
  ENTITY_ID      NUMBER,
  PAYLOAD        CLOB,
  CREATED_AT     TIMESTAMP      DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT PK_LOGIS_EVENT_LOG PRIMARY KEY (ID)
);
/
```

Ключевые правила:
- Нормализованные таблицы, не KV/blob
- Разделение: master data, settings, documents, document items, event log
- `CHAR(1)` для флагов (`IS_ACTIVE`), `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- Primary key на sequence + trigger auto-ID
- Foreign keys между таблицами модуля

### 8.3 Зарегистрировать DDL в deploy

Добавить новые файлы в массив `order` в `deploy_oracle_objects.py`:

```python
order = [
    ...existing files...
    "40_logis_tables.sql",
    "41_logis_views.sql",
    "42_logis_triggers.sql",
    "43_logis_demo_data.sql",
]
```

Выполнить:

```bash
python deploy_oracle_objects.py
```

### 8.4 Создать модель (Oracle store)

Создать `models/logis_oracle_store.py`:

```python
"""
Нормализованное Oracle-хранилище модуля LOGIS.
"""
from models.database import DatabaseModel


class LogisStore:
    """CRUD для таблиц LOGIS_*."""

    @staticmethod
    def get_warehouses(active_only=True):
        with DatabaseModel() as db:
            sql = "SELECT ID, CODE, NAME, IS_ACTIVE FROM LOGIS_WAREHOUSES"
            if active_only:
                sql += " WHERE IS_ACTIVE = 'Y'"
            sql += " ORDER BY NAME"
            result = db.execute_query(sql)
            if not result.get("success"):
                return []
            cols = result.get("columns", [])
            return [dict(zip(cols, row)) for row in result["data"]]

    @staticmethod
    def create_order(warehouse_id, order_no):
        with DatabaseModel() as db:
            sql = """
                INSERT INTO LOGIS_ORDERS (ID, ORDER_NO, WAREHOUSE_ID)
                VALUES (LOGIS_ORDERS_SEQ.NEXTVAL, :order_no, :wh_id)
                RETURNING ID INTO :out_id
            """
            # используйте db.execute_dml() или аналог из DatabaseModel
            ...
```

Смотрите `models/decor_oracle_store.py` и `models/agro_oracle_store.py` как эталон.

### 8.5 Создать контроллер

Создать `controllers/logis_controller.py`:

```python
"""
Контроллер модуля LOGIS: бизнес-логика + API.
"""
from models.logis_oracle_store import LogisStore


class LogisController:
    @staticmethod
    def get_warehouses():
        return LogisStore.get_warehouses()

    @staticmethod
    def get_orders(warehouse_id=None):
        return LogisStore.get_orders(warehouse_id)
```

### 8.6 Добавить маршруты в app.py

В `app.py`:

```python
from controllers.logis_controller import LogisController

# UI routes
@app.route('/UNA.md/orasldev/logis')
def logis_main():
    if not AuthController.is_authenticated():
        return _login_redirect()
    return render_template('logis_main.html')

# API routes
@app.route('/api/logis/warehouses')
def api_logis_warehouses():
    if not AuthController.is_authenticated():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(LogisController.get_warehouses())
```

Все UI под `/UNA.md/orasldev/logis*`, все API под `/api/logis/*`.

### 8.7 Создать HTML шаблон

Создать `templates/logis_main.html`. Использовать существующие шаблоны как образец (например `colass_catalog.html` или `agro_admin.html`).

### 8.8 Зарегистрировать в Shell

Добавить INSERT в демо-данные или выполнить вручную:

```sql
INSERT INTO UNA_SHELL_PROJECTS (SLUG, NAME, DESCRIPTION, DASHBOARD_IDS, SORT_ORDER, IS_ACTIVE)
VALUES ('logis', 'Логистика', 'Модуль логистики', '00,01', 40, 'Y');
COMMIT;
```

### 8.9 Добавить в version_registry.py

В `version_registry.py` -> `_default_manifest()` -> `modules`:

```python
"logis": {"name": "Logistics", "version": "0.1.0", "updated_at": ts, "notes": "Warehouse logistics"},
```

### 8.10 Обновить документацию

1. Обновить `DEVELOPER_GUIDE.md` (этот файл): добавить раздел модуля в секцию 2
2. Обновить `README.md`: добавить модуль в список возможностей
3. Создать `docs/Logis/README.md` с описанием Oracle-объектов, маршрутов, API
4. Обновить `sql/README.md`: добавить скрипты модуля

### 8.11 Checklist перед merge

- [ ] DDL-файлы в `sql/` на git
- [ ] DDL-файлы добавлены в `deploy_oracle_objects.py`
- [ ] `python deploy_oracle_objects.py` выполняется без ошибок
- [ ] Oracle-объекты видны в `SELECT * FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'LOGIS_%'`
- [ ] Контроллер создан, импортирован в `app.py`
- [ ] UI маршруты под `/UNA.md/orasldev/logis*`
- [ ] API маршруты под `/api/logis/*`
- [ ] HTML-шаблон создан и отображается
- [ ] Модуль зарегистрирован в `UNA_SHELL_PROJECTS`
- [ ] Модуль добавлен в `version_registry.py`
- [ ] Нет SQLite/JSON primary storage
- [ ] Нет generic KV-таблиц (`APP_RUNTIME_KV`)
- [ ] `README.md` обновлён
- [ ] `DEVELOPER_GUIDE.md` обновлён
- [ ] Локальный запуск `./run_local.sh` работает, модуль отвечает

---

## 9. Запрещённые паттерны

1. `APP_RUNTIME_KV`, `MODULE_RUNTIME_KV` -- generic KV-таблицы для primary state
2. `APP_EVENT_LOG` как общий контейнер для разных доменов
3. JSON blob в одном CLOB-поле как модель всего модуля
4. `data/*.json`, `data/*.jsonl`, SQLite как authoritative storage для бизнес-данных
5. Модуль без DDL, без Oracle prefix, без документации
6. Remote `.env` с `WALLET_DIR` внутри каталога деплоя (на remote всегда абсолютный путь)
7. Wallet в Git

---

## 10. Полезные команды

```bash
# Запуск локально
./run_local.sh

# Deploy на remote
./deploy_to_remote.sh

# Deploy Oracle DDL
python deploy_oracle_objects.py
python deploy_oracle_objects.py --drop      # Полное пересоздание
python deploy_oracle_objects.py --dry-run   # Только показать

# Deploy Oracle DDL на remote
DEPLOY_ORACLE_ON_REMOTE=1 ./deploy_to_remote.sh

# Просмотр логов (remote, через SSH)
ssh ubuntu@92.5.3.187 'tail -f /home/ubuntu/artgranit/app.log'

# Перезапуск remote-сервера
ssh ubuntu@92.5.3.187 'cd ~/artgranit && ./full_restart.sh'

# Проверка Oracle-объектов из Python
python -c "
from models.database import DatabaseModel
with DatabaseModel() as db:
    r = db.execute_query(\"SELECT OBJECT_TYPE, OBJECT_NAME FROM USER_OBJECTS ORDER BY OBJECT_TYPE, OBJECT_NAME\")
    for row in r.get('data', []):
        print(row)
"
```
