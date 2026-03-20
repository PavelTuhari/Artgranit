# Artgranit OCI — Oracle SQL Developer Web & Dashboard

Веб-приложение для управления и мониторинга Oracle Autonomous Database (OCI), а также бизнес-модулей: Nufarul (химчистка/прачечная), Кредиты, DECOR, мультипроектный Shell и документация.

## Важные инварианты проекта

Ниже правила, которые обязательны при добавлении новых модулей. Они зафиксированы, чтобы не возвращаться к уже устраненным ошибкам архитектуры.

1. Все рабочие данные модулей хранятся в Oracle.
2. SQLite, JSON-файлы, JSONL и CLOB/KV-хранилища не используются как primary storage для бизнес-состояния.
3. Таблицы новых модулей должны быть в нормальной форме. Нельзя хранить весь state модуля одним JSON blob в одной таблице.
4. У каждого модуля должен быть свой префикс Oracle-объектов. Примеры: `CRED_*`, `NUF_*`, `DECOR_*`.
5. Если модулю нужен event log, он должен быть отдельным append-only логом, а не заменой нормализованной модели данных.
6. Кодовый deploy на remote и deploy Oracle DDL считаются разными шагами. `deploy_to_remote.sh` по умолчанию не накатывает DDL в Oracle.
7. Рабочий web-префикс приложения: `/UNA.md/orasldev/...`. Путь `/UNA.md/` сам по себе не является точкой входа.
8. Oracle wallet на remote должен жить вне каталога деплоя или явно сохраняться и восстанавливаться при обновлении кода.

## 🚀 Основные возможности

1.  **SQL Worksheet (Oracle SQL Developer):**
    *   Выполнение произвольных SQL-запросов.
    *   Просмотр результатов в табличном виде.
    *   Браузер объектов БД (Таблицы, Представления, Процедуры, Функции) в левой панели.
    *   Интерфейс MDI (Multiple Document Interface) — плавающие окна.

2.  **Dashboard (Мониторинг):**
    *   **Real-time метрики:** CPU, RAM, Сессии (обновление через WebSockets).
    *   **Top SQL:** Мониторинг тяжелых запросов.
    *   **Tablespaces:** Заполненность табличных пространств.
    *   Конфигурируемые дашборды (виджеты, custom SQL).

3.  **Nufarul (химчистка / прачечная):**
    *   **Админка** (`/UNA.md/orasldev/nufarul-admin`): услуги (по группам), статусы заказов, заказы, отчёты. Языки RU/RO/EN.
    *   **Оператор** (`/UNA.md/orasldev/nufarul-operator`): приём заказов в зале — выбор услуг, клиент, создание заказа, поиск по штрихкоду.
    *   **Первичные документы (печать):** Bon de Comandă, Comandă (заказ), Jurnal Registru (журнал регистраций) — генерация HTML по шаблонам из данных заказа.

4.  **Кредиты:** админка программ/банков/матрицы, оператор оформления заявок, интеграции EasyCredit и Iute, портфель «Бомба», настраиваемые отчёты.

5.  **DECOR:** оператор, админка, расчёт заказов, печатные документы, нормализованное хранение материалов, настроек, заказов и раздвижных систем в Oracle.

6.  **Документация:**
    *   Индекс документации (`/UNA.md/orasldev/docs`), просмотр Markdown, ТЗ Nufarul.
    *   Материалы DECOR и HTML-конверсии (`/UNA.md/orasldev/docs/decor`).
    *   Материалы Nufarul: список файлов, просмотр XLSX/DOC/PDF, галерея JPG (`docs_jpg`) с описаниями по смыслу и OCR-таблицами, Registru Documente.

7.  **Системные функции:**
    *   Страница диагностики и управления сервером (`/test.html`).
    *   Авторизация, смена языка (RU/RO/EN).

---

## 🛠 Архитектура

Проект построен на паттерне **MVC** (Model-View-Controller):

*   **Backend:** Python + Flask.
*   **Real-time:** Flask-SocketIO (WebSockets) + Threading.
*   **Database Driver:** `oracledb` (Thick/Thin mode) с использованием Oracle Wallet.
*   **Frontend:** HTML5, CSS3, Vanilla JS, Socket.io-client.
*   **Runtime persistence:** Oracle-first. Бизнес-состояние модулей хранится в нормализованных Oracle-таблицах.

### Структура проекта

```text
Artgranit/
├── app.py                  # Точка входа, маршруты, SocketIO
├── config.py               # Конфигурация (.env, БД, API)
├── requirements.txt
├── README.md
│
├── controllers/
│   ├── auth_controller.py
│   ├── dashboard_controller.py
│   ├── sql_controller.py
│   ├── objects_controller.py
│   ├── credit_controller.py
│   ├── nufarul_controller.py   # Услуги, заказы, статусы, отчёты
│   ├── documentation_controller.py
│   └── shell_controller.py
│
├── models/
│   ├── database.py         # Connection Pool, Oracle
│   ├── combo_scenario.py
│   ├── shell_project.py
│   ├── oracle_runtime_store.py   # append-only runtime/event log helper
│   └── decor_oracle_store.py     # нормализованное Oracle-хранилище DECOR
│
├── templates/
│   ├── login.html          # Вход в проект (Artgranit OCI)
│   ├── sqldeveloper_mdi.html
│   ├── dashboard_mdi.html
│   ├── nufarul_admin.html, nufarul_operator.html
│   ├── nufarul/            # Первичные документы: document_bon_comanda.html, document_comanda.html, document_jurnal_registru.html
│   ├── credit_*.html, shell_*.html
│   ├── docs_index.html, docs_viewer.html
│   └── test.html
│
├── docs/                   # Документация
│   ├── PROJECT_DOCUMENTATION.html   # Для Claude Code
│   ├── dashboards/
│   └── Nufarul/            # ТЗ, каталоги, docs_jpg (галерея + OCR, Registru)
│
├── sql/                    # DDL Oracle (bus, cred, nuf, decor)
├── integrations/           # easycredit_client.py, iute_client.py
├── services/               # credit_logger, report_export
├── scripts/                # ocr_docs_jpg_to_tables.py
└── Wallet_DBManager/       # или WALLET_DIR из .env
```

### Ключевые технические решения

1.  **Connection Pool:** В `models/database.py` используется пул соединений (размер 2-10). Это критично для производительности, чтобы не открывать SSL-соединение с Oracle Cloud на каждый запрос.
2.  **Оптимизация Top SQL:** Запрос к `v$sqlarea` упрощен (убран тяжелый `sql_text`, добавлен таймаут), чтобы не вешать дашборд при нагрузке.
3.  **Test Page:** Страница `/test.html` работает автономно и позволяет перезапустить Python-процесс сервера прямо из браузера в случае зависания.
4.  **Нормализованное хранение модулей:** DECOR хранится в `DECOR_*` таблицах, а кредитный runtime log — в `CRED_EVENT_LOG`. Это эталон для новых модулей.

## Правила добавления нового модуля

### 1. Данные и схема Oracle

При добавлении нового модуля:

1. Создайте отдельные Oracle-таблицы с собственным префиксом модуля.
2. Разбейте данные по сущностям, справочникам, настройкам, документам и строкам документов.
3. Не используйте одну таблицу вида `MODULE_RUNTIME_KV` для хранения всего состояния модуля.
4. Не храните бизнес-данные в файлах `data/*.json`, `data/*.jsonl`, SQLite или в CLOB-полях как единый blob.
5. Добавьте DDL в `sql/` и включите новый SQL-файл в порядок выполнения в `deploy_oracle_objects.py`.

### 2. Именование объектов

1. Используйте единый короткий префикс модуля в Oracle-объектах.
2. Примеры корректного именования:
    `DECOR_ORDERS`, `DECOR_ORDER_ITEMS`, `CRED_EVENT_LOG`, `NUF_SERVICES`.
3. Не создавайте generic-объекты вида `APP_RUNTIME_KV`, `APP_EVENT_LOG`, `MODULE_STATE_JSON`.

### 3. Runtime и логи

1. Append-only логи допустимы отдельной таблицей, если это именно журнал событий.
2. Event log не должен подменять нормализованную модель предметной области.
3. Если модулю нужен storage helper, он должен писать в таблицы модуля или в явно выделенный log table, а не в generic KV storage.

### 4. UI, маршруты и dashboards

1. Добавьте маршруты в `app.py` под префиксом `/UNA.md/orasldev/...`.
2. Если модуль отображается в dashboards, обновите соответствующие `dashboards/dashboard_*.json`.
3. Если добавлен новый embedded UI, добавьте документацию в `docs/dashboards/` и ссылки в docs index.
4. Проверяйте, что в dashboards и docs не осталось ссылок на старые generic runtime-таблицы или устаревшие URL.

### 5. Документация и проверка

Каждый новый модуль должен сопровождаться:

1. описанием Oracle-объектов и их префикса;
2. маршрутов UI и API;
3. инструкцией локального запуска;
4. инструкцией деплоя на remote;
5. коротким checklist проверки после релиза.

Минимальная проверка перед merge/deploy:

1. по коду нет ссылок на SQLite/JSON primary storage для нового модуля;
2. Oracle-объекты модуля реально созданы и видимы в `USER_TABLES`/`USER_OBJECTS`;
3. локальные и удалённые URL модуля отвечают;
4. dashboards/docs обновлены;
5. deploy не оставляет модуль в полу-локальном, полу-Oracle состоянии.

---

## ⚙️ Установка и Запуск

### Предварительные требования
*   Ubuntu Server
*   Python 3.12+ на remote
*   Python 3.9+ для локального окружения проекта
*   Oracle Wallet (ZIP архив)

### Установка

1.  **Подготовка окружения:**
    ```bash
    cd /home/ubuntu/artgranit
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Настройка:**
    Убедитесь, что файлы кошелька распакованы в папку, указанную в `config.py` (`WALLET_DIR`).

### Oracle wallet на remote server

Для удалённого сервера Oracle wallet должен считаться отдельным инфраструктурным артефактом, а не частью application bundle.

Правильный вариант:

1. хранить wallet вне каталога `/home/ubuntu/artgranit`;
2. задавать `WALLET_DIR` абсолютным путём в remote `.env`;
3. не рассчитывать на то, что wallet будет приезжать вместе с кодовым deploy.

Текущий production-путь:

```bash
WALLET_DIR=/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q
```

Почему это важно:

1. `deploy_to_remote.sh` пересобирает каталог проекта;
2. relative path вроде `WALLET_DIR=wallet_HXPAVUNKCLU9HE7Q` может быть потерян при полном обновлении remote tree;
3. wallet не должен зависеть от того, был ли он включён в архив кода.

### Запуск сервера

#### Локальный запуск на Mac (localhost:3003)

Для локальной разработки на Mac:

```bash
cd /Users/pt/Projects.AI/Artgranit
./run_local.sh
```

Или вручную:

```bash
cd /Users/pt/Projects.AI/Artgranit
source .venv_run/bin/activate
export ENVIRONMENT=LOCAL
export PORT=3003
export SERVER_HOST=127.0.0.1
python3 app.py
```

Приложение будет доступно по адресу: `http://localhost:3003`

#### Удаленный сервер (Production режим)

Для запуска на удаленном сервере в фоновом режиме:

```bash
cd /home/ubuntu/artgranit
./full_restart.sh
```

Или вручную:

```bash
cd /home/ubuntu/artgranit
source venv/bin/activate
export ENVIRONMENT=REMOTE
export PORT=8000
nohup python3 app.py > app.log 2>&1 &
```

Приложение будет доступно по адресу: `http://92.5.3.187:8000`

Рабочие URL после запуска:

*   `http://92.5.3.187:8000/login`
*   `http://92.5.3.187:8000/UNA.md/orasldev/`

Путь `http://92.5.3.187:8000/UNA.md/` не является отдельным маршрутом и может возвращать `404`.

### Кодовый deploy на remote

Штатный способ обновить удаленный сервер:

```bash
./deploy_to_remote.sh
```

Что делает скрипт:

1. делает backup remote-проекта, если он уже существует;
2. копирует новый код на сервер;
3. сохраняет remote `.env`;
4. если `WALLET_DIR` указывает на относительный путь внутри проекта, временно сохраняет и восстанавливает wallet-каталог;
5. устанавливает зависимости;
6. перезапускает `app.py`.

Предпочтительный вариант всё равно такой:

1. wallet живёт вне `$REMOTE_PATH`;
2. `WALLET_DIR` задан абсолютным путём;
3. deploy кода не отвечает за доставку секретов и wallet-файлов.

Что скрипт не делает по умолчанию:

1. не накатывает Oracle DDL;
2. не пересоздаёт Oracle-объекты автоматически.

Если для нового модуля добавлены DDL-скрипты, их нужно разворачивать отдельно:

```bash
python deploy_oracle_objects.py
```

Или на remote при явной необходимости:

```bash
DEPLOY_ORACLE_ON_REMOTE=1 ./deploy_to_remote.sh
```

---

## 🔧 Обслуживание и Troubleshooting

### 1. Как проверить статус?
Откройте в браузере: `http://IP_ADDRESS:8000/test.html`
*   Нажмите **"Проверить подключение"**, чтобы протестировать связь с БД.
*   Нажмите **"Вход в систему"**, чтобы перейти к приложению.

### 2. Как перезапустить сервер?
**Способ А (через браузер):**
Зайдите на `/test.html` и нажмите красную кнопку **"🔄 Перезапустить Python сервер"**.

**Способ Б (через SSH):**
Если интерфейс недоступен, выполните команду одной строкой:

```bash
pkill -f "python3 app.py"; sleep 2; cd /home/ubuntu/artgranit && source venv/bin/activate && nohup python3 app.py > app.log 2>&1 &
```

### Быстрый перезапуск (Скрипт)

Для полного сброса и чистого перезапуска сервера используйте скрипт `full_restart.sh`. Он автоматически убьет зависшие процессы, освободит порт 8000 и перезапустит приложение.

1.  **Запуск из папки проекта:**
    ```bash
    ./full_restart.sh
    ```

2.  **Запуск одной командой через SSH (с локальной машины):**
    ```bash
    ssh -i 'путь/к/ключу.key' ubuntu@92.5.3.187 'cd ~/artgranit && ./full_restart.sh'
    ```

### 3. Ошибка "Port 8000 is in use"
Если сервер не запускается из-за занятого порта, убейте зависшие процессы:

```bash
# Найти процесс
sudo fuser -k 8000/tcp
# ИЛИ убить все процессы python и http.server
sudo pkill -f "python3"
sudo pkill -f "http.server"
```

### 4. Просмотр логов
Чтобы увидеть ошибки в реальном времени:

```bash
tail -f /home/ubuntu/artgranit/app.log
```

---

## 🔐 Учетные данные (Config)

Основные настройки находятся в `config.py`.
*   **DB_USER**: ADMIN
*   **CONNECT_STRING**: Строка подключения из tnsnames.ora (High/Medium/Low)
*   **WALLET_DIR**: Путь к папке с кошельком

### Документация и вход

*   **Вход в проект:** страница `/login` — заголовок «Artgranit OCI», подзаголовок с перечислением модулей (Oracle SQL Developer, Dashboard, Nufarul, Кредиты, Документация). Язык интерфейса: RU / RO / EN.
*   **Документация для разработчиков и Claude:** в приложении — раздел «Документация» → «Документация проекта (Claude Code)», либо файл `docs/PROJECT_DOCUMENTATION.html` — единый HTML с описанием структуры, маршрутов, конфигурации, первичных документов Nufarul (Bon de Comandă, Comandă, Jurnal Registru).

## Антипаттерны, запрещенные для новых модулей

1. Generic Oracle KV-таблицы для хранения состояния модуля.
2. Хранение заказов, настроек, материалов и справочников внутри одного JSON/CLOB поля.
3. Смешанная схема, где часть state живёт в Oracle, а часть остаётся authoritative в локальном JSON-файле.
4. Незадокументированные маршруты, объекты Oracle или DDL-файлы.
5. Деплой нового модуля без явной проверки, что remote URL и Oracle-объекты обновлены согласованно.
6. Remote `.env` с `WALLET_DIR`, указывающим на временный или удаляемый путь внутри каталога деплоя.

*Разработано в рамках проекта Artgranit OCI.*
