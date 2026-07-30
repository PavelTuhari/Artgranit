# Biro26 × EasyCredit/Iute — интеграция кредитных провайдеров

**Дата:** 2026-07-31
**Статус:** утверждён, готов к планированию реализации

## 1. Задача

1. Восстановить и обновить документацию `https://nufarul.eminescu.md/UNA.md/orasldev/docs/easycredit`.
2. Перенести библиотеку кредитных провайдеров (EasyCredit SOAP, Iute REST), обкатанную в демо `/UNA.md/orasldev/credit-easycredit` и `/UNA.md/orasldev/credit-iute`, в бэк-офис Biro26; настройки хранить в Oracle в таблицах с префиксом `TMS_CREDITE_*`.
3. Подключить EasyCredit (и любого другого сконфигурированного провайдера) во фронт-офис Biro26 как опцию оплаты, доступную клиенту, если соответствующие настройки сделаны в бэк-офисе.

## 2. Исходное состояние

### Основной проект (Artgranit, Oracle ADB, thin-mode + wallet)

- `integrations/base_provider.py` — абстракция `CreditProvider` + `ProviderRegistry` (singleton).
- `integrations/easycredit_client.py` (536 строк) — SOAP-клиент: `preapproved`, `submit_request`, `status`, `client_info`.
- `integrations/iute_client.py` (162 строки) — REST-клиент: `check_auth`, `create_order`, `order_status`.
- `integrations/easycredit_provider.py`, `integrations/iute_provider.py` — реализации `CreditProvider`.
- `integrations/__init__.py` — авторегистрация обоих провайдеров в глобальном `registry`.
- Демо-страницы: `templates/credit_easycredit.html`, `templates/credit_iute.html`; API `/api/credit-easycredit/*`, `/api/credit-iute/*` в `app.py` с mock-фолбэком при отсутствии кредов.
- Настройки: `data/easycredit_settings.json`, `data/iute_settings.json` (читаются `config.py`), поверх `.env`. **Нарушает CLAUDE.md** (file-based authoritative state).

### Biro26 / OfficePlus (Oracle 11g, thick-mode subprocess worker, CL8MSWIN1251)

- `sql/biro26/10_ybiro_credit.sql` — `YBIRO_CREDIT_ORG`, `YBIRO_CREDIT_PLAN`; `YBIRO_DOC_META` расширена `CREDIT_PLAN_ID/MONTHS/AVANS`. `YBIRO_CREDIT_REQ` создана отдельно.
- `models/biro26_credit.py` — CRUD организаций/пакетов, `calc()` (оценочный расчёт рассрочки), `request_create()`.
- Админка `/UNA.md/orasldev/biro26-credit-admin` (`templates/biro26/credit_admin.html`), API `/api/biro26/credit/*`.
- `ORG_MODE='api'` существует, но реального адаптера нет: `request_create()` делает безусловный `POST` произвольного JSON на `API_URL`.
- Фронт-офис (`templates/biro26/site_cart.html`, `templates/biro26/shop.html`) уже умеет выбирать «Rate / credit», считать плитки сроков и слать «Cerere de credit EasyCredit» — но это лишь уведомление магазину, без обращения к API.

### Дефект документации

`app.py:869` и `app.py:881` читают `docs/project_easycredit.html` и `docs/project_iute.html`, тогда как файлы лежат в `docs/CREDITE/`. Обе страницы отдают 404.

## 3. Принятые решения

| Решение | Выбор |
|---|---|
| Схема | Единая `TMS_CREDITE_*`: провайдеры, организации, пакеты, заявки, лог событий |
| Судьба `YBIRO_CREDIT_*` | Данные мигрируют в `TMS_CREDITE_*`, старые таблицы переименовываются в `*_OLD`, не дропаются |
| Размещение | Один и тот же DDL разворачивается **в обе БД**: ADB (основной проект) и 11g (Biro26). Каждый контур читает свою БД — нет кросс-БД зависимости, креды могут различаться (у Biro26 свой POS/договор) |
| Источник настроек | `data/*.json` перестаёт быть авторитетным: одноразовый seed при деплое, дальше только Oracle с фолбэком на `.env` |
| Фронт-офис | Полный флоу в корзине: форма → `preapproved` → `submit` → опрос `status`; провайдер-агностично — показываются все организации со сконфигурированным провайдером |

Оговорка: `TMS_` — родной префикс вендора OfficePlus. Приложенческие таблицы попадают в его пространство имён по явному требованию заказчика.

## 4. Схема данных

Один логический DDL, два физических файла (различия только в синтаксисе, совместимом с 11g — без identity-колонок, последовательности + `BEFORE INSERT` триггеры).

### `TMS_CREDITE_PROVIDER`

Реестр API-провайдеров.

| Колонка | Тип | Описание |
|---|---|---|
| `ID` | NUMBER PK | |
| `CODE` | VARCHAR2(30) UNIQUE NOT NULL | `easycredit`, `iute` — совпадает с `CreditProvider.id` |
| `NAME` | VARCHAR2(100) NOT NULL | Отображаемое имя |
| `ENABLED` | VARCHAR2(1) DEFAULT '0' | |
| `ENV` | VARCHAR2(20) DEFAULT 'sandbox' | `sandbox` \| `production` |
| `BASE_URL` | VARCHAR2(400) | |
| `ICON` | VARCHAR2(20) | Эмодзи для UI |
| `COLOR` | VARCHAR2(20) | HEX |
| `INFO` | VARCHAR2(2000) | |
| `ORD` | NUMBER DEFAULT 0 | |
| `UPDATED` | DATE DEFAULT SYSDATE | |

### `TMS_CREDITE_PROVIDER_PARAM`

Параметры и креды провайдера. Child-таблица значений (паттерн `DECOR_SETTINGS` из CLAUDE.md), а не JSON blob и не глобальный KV.

| Колонка | Тип | Описание |
|---|---|---|
| `PROVIDER_ID` | NUMBER NOT NULL | FK → `TMS_CREDITE_PROVIDER(ID)` |
| `PARAM_NAME` | VARCHAR2(40) NOT NULL | `api_user`, `api_password`, `api_key`, `pos_identifier`, `salesman_identifier` |
| `PARAM_VALUE` | VARCHAR2(400) | |
| `IS_SECRET` | VARCHAR2(1) DEFAULT '0' | Секреты маскируются в GET-ответах API |

PK `(PROVIDER_ID, PARAM_NAME)`.

### `TMS_CREDITE_ORG`

Организации кредитования. Перенос `YBIRO_CREDIT_ORG` один-в-один плюс `PROVIDER_ID`.

Колонки: `ID` PK, `NAME` NOT NULL, `ENABLED`, `ORG_MODE` (`manual`\|`api`), `PROVIDER_ID` (FK, nullable — `NULL` означает ручной режим), `API_URL` (legacy generic webhook, сохраняется для совместимости), `LOGO_URL`, `INFO`, `ORD`.

### `TMS_CREDITE_PLAN`

Пакеты рассрочки. Полный перенос `YBIRO_CREDIT_PLAN`; **формула расчёта не меняется**:

```
credit_price = price * (1 + MARKUP_PCT/100)
financed     = credit_price - avans
monthly      = financed/months
             + financed * ANNUAL_PCT/12/100
             + financed * MONTHLY_FEE_PCT/100
total        = avans + monthly*months + ISSUE_FEE
```

Колонки: `ID` PK, `ORG_ID` FK, `NAME`, `MONTHS_MIN`, `MONTHS_MAX`, `AMOUNT_MIN`, `AMOUNT_MAX`, `MARKUP_PCT`, `ANNUAL_PCT`, `MONTHLY_FEE_PCT`, `ISSUE_FEE`, `AVANS_MIN_PCT`, `ENABLED`, `INFO`.

### `TMS_CREDITE_REQ`

Заявки. Перенос `YBIRO_CREDIT_REQ` плюс поля API-флоу.

Существующие: `ID` PK, `ORG_ID`, `PLAN_ID`, `MONTHS`, `PRODUCT_COD`, `PRODUCT_NAME`, `QTY`, `AMOUNT`, `CREDIT_PRICE`, `MONTHLY`, `CLIENT_NAME`, `PHONE`, `STATUS`, `CREATED`.

Добавляемые:

| Колонка | Тип | Описание |
|---|---|---|
| `PROVIDER_CODE` | VARCHAR2(30) | Через какого провайдера ушла заявка |
| `EXT_REF` | VARCHAR2(120) | URN (EasyCredit) или `order_id` (Iute) |
| `API_STATUS` | VARCHAR2(60) | Последний статус от провайдера |
| `PREAPPROVED_AMOUNT` | NUMBER | Результат `preapproved` |
| `IDNP_MASKED` | VARCHAR2(20) | Только маска — полный IDNP не хранится |
| `LAST_CHECK` | DATE | Время последнего опроса статуса |

### `TMS_CREDITE_REQ_EVENT`

Append-only лог обращений к API. Заменяет нынешнее `API_RESULT VARCHAR2(400)`.

Колонки: `ID` PK, `REQ_ID` FK (nullable — вызовы до создания заявки, например `preapproved`), `PROVIDER_CODE`, `OP` (`preapproved`\|`submit`\|`status`\|`check_auth`), `HTTP_CODE` NUMBER, `DURATION_MS` NUMBER, `PAYLOAD` CLOB, `RESULT` CLOB, `IS_ERROR` VARCHAR2(1), `CREATED` DATE DEFAULT SYSDATE.

Персональные данные в `PAYLOAD` маскируются перед записью (IDNP, полный телефон).

### Миграция

1. Создать `TMS_CREDITE_*`.
2. `INSERT ... SELECT` из `YBIRO_CREDIT_ORG` / `PLAN` / `REQ` с сохранением `ID`; последовательности перезапустить со `MAX(ID)+1`.
3. Перенести значения из `data/easycredit_settings.json` / `data/iute_settings.json` (и переменных `.env`) в `TMS_CREDITE_PROVIDER(_PARAM)` — только если строк ещё нет.
4. `RENAME YBIRO_CREDIT_ORG TO YBIRO_CREDIT_ORG_OLD` и т.д. Ничего не дропается.

Шаг идемпотентен: повторный запуск на уже мигрированной БД ничего не меняет.

## 5. Код

### `models/credite_settings.py` (новый)

Единая точка чтения/записи настроек провайдеров поверх двух коннекторов.

```
class CrediteBackend(ABC):        # execute_query / execute_dml
class AdbBackend(CrediteBackend)      # models/database.py
class Biro26Backend(CrediteBackend)   # models/biro26_db.py (subprocess worker)

class CrediteSettings:
    def __init__(self, backend)
    def get(code) -> dict | None        # провайдер + параметры
    def list_all(include_disabled=True) -> list[dict]
    def save(code, *, enabled, env, base_url, params: dict) -> dict
    #   пустое значение секретного параметра = «не менять»
    def masked(code) -> dict            # секреты как 'abc***'
```

Кэш в памяти с TTL 60 с, ключ `(backend_id, code)`; сбрасывается при `save()`.

### `integrations/` (правки)

- `CreditProvider.__init__(self, settings_source=None)`; методы `_base_url()`, `_user()` и т.д. читают из `settings_source`, если он передан, иначе — из `Config` (текущее поведение).
- Фабрика `integrations.build_registry(settings_source) -> ProviderRegistry` — для Biro26.
- Глобальный `registry` в `__init__.py` остаётся, но инициализируется источником ADB.
- `easycredit_client.py` и `iute_client.py` **не меняются** — библиотека переиспользуется как есть.

### `config.py` (правки)

- `Config.easycredit_*` / `Config.iute_*` читают через `CrediteSettings(AdbBackend())`, фолбэк на `.env` при недоступности БД или отсутствии строки.
- `save_easycredit_settings()` / `save_iute_settings()` пишут в Oracle.
- Чтение `data/*.json` остаётся только в функции одноразового seed, вызываемой скриптом деплоя.

### `models/biro26_credit.py` (правки)

- Все запросы переводятся на `TMS_CREDITE_*`.
- Новые методы, работающие через `build_registry(Biro26Backend())`:
  - `api_preapproved(org_id, idnp, amount)` → `{preapproved, max_amount, message}`
  - `api_submit(req_payload)` → создаёт строку `TMS_CREDITE_REQ`, вызывает провайдера, сохраняет `EXT_REF`
  - `api_status(req_id | ext_ref)` → обновляет `API_STATUS`, `LAST_CHECK`
- Каждый вызов пишет строку в `TMS_CREDITE_REQ_EVENT` (операция, длительность, код, маскированный payload, результат).
- При ошибке или неконфигурированном провайдере — деградация на существующий флоу «уведомление магазину», без исключения наружу.

### `app.py` (правки)

Новые роуты:

```
GET    /api/biro26/credit/providers               — список + маскированные настройки
PUT    /api/biro26/credit/providers/<code>        — сохранить настройки
POST   /api/biro26/credit/providers/<code>/test   — check_auth
POST   /api/biro26/credit/api/preapproved
POST   /api/biro26/credit/api/submit
GET    /api/biro26/credit/api/status
GET    /api/biro26/credit/requests/<id>/events    — лог событий заявки
```

Админские роуты требуют авторизации. Публичные (`/api/biro26/credit/api/*`) — без авторизации, но под существующим `flask_limiter` (`limiter`, `app.py:74`) с лимитом по IP и без выдачи кредов наружу.

Фикс: `docs_easycredit()` и `docs_iute()` читают `docs/CREDITE/project_*.html`.

## 6. Бэк-офис Biro26

`templates/biro26/credit_admin.html` — новая вкладка **«Provideri API»**:

- Карточка на провайдера: вкл/выкл, `env` (sandbox/production), `base_url`, поля параметров. Секреты показываются маской; пустое поле при сохранении означает «не менять».
- Кнопка **«Test conexiune»** → `check_auth`, показывает результат и длительность.
- В форме организации — селект «Provider API»; пусто = ручной режим.
- Вкладка «Cereri» дополняется колонками `EXT_REF`, `API_STATUS`, кнопкой «Обновить статус» и раскрывающимся логом `TMS_CREDITE_REQ_EVENT`.

## 7. Фронт-офис Biro26

`templates/biro26/site_cart.html` (основной сценарий) и `templates/biro26/shop.html` (модалка товара).

`GET /api/biro26/credit/offers` дополняется полем `provider` у организации (`code`, `name`, `icon`, `configured`).

Когда выбран способ оплаты «Rate / credit» и у организации есть `provider.configured == true`:

1. Форма: ФИО, телефон, IDNP.
2. **«Проверить предодобрение»** → `POST /api/biro26/credit/api/preapproved` → «Предодобрено до X лей» либо отказ с объяснением.
3. **«Отправить заявку»** → `POST /api/biro26/credit/api/submit` → показ `EXT_REF` (URN).
4. Автоопрос `GET /api/biro26/credit/api/status` каждые 5 с, максимум 2 минуты, затем — «проверьте статус позже, менеджер свяжется с вами».

Если `provider.configured == false` либо любой вызов API упал — показывается текущая кнопка «Cerere de credit», существующий флоу не ломается. Дисклеймер об оценочном характере расчёта сохраняется.

Тексты — RO/RU, как в остальном модуле.

## 8. Документация

- Фикс путей в `app.py` для `/docs/easycredit` и `/docs/iute`.
- `docs/CREDITE/project_easycredit.html` переписывается: SOAP-операции EasyCredit, слой `CreditProvider`/`ProviderRegistry`, схема `TMS_CREDITE_*`, настройка в бэк-офисе Biro26, флоу витрины, локальный запуск, remote deploy, checklist верификации.
- `docs/CREDITE/project_iute.html` — аналогичное обновление раздела настроек (переход с JSON на Oracle).
- Обновляются: `README.md`, `docs/Biro26/README_BIRO26.html`, `docs/CREDITE/PROJECT_DOCUMENTATION.html`.

## 9. Деплой

- `sql/50_credite_tables.sql` — DDL для ADB, включается в порядок выполнения `deploy_oracle_objects.py`.
- `sql/biro26/12_tms_credite.sql` — DDL для 11g (номера 10 и 11 заняты `10_ybiro_credit.sql` и `11_ybiro_credit_req.sql`).
- `deploy_credite_oracle.py --target adb|biro26|both` — идемпотентный DDL + миграция + seed, по образцу `deploy_biro26_app_tables.py`.
- `deploy_to_remote.sh` переносит только код; DDL запускается отдельно.

## 10. Тесты и верификация

- `test_credite_settings.py` — roundtrip сохранения/чтения настроек, маскирование секретов, семантика «пустое = не менять», фолбэк на `.env` при недоступной БД.
- Расширение `test_biro26_smoke.py` — `TMS_CREDITE_*` существуют, `public_offers()` отдаёт поле `provider`, `calc()` даёт те же числа, что и до миграции.
- Провайдеры тестируются против мока (sandbox-креды в CI отсутствуют).

Checklist после релиза:

1. `python deploy_credite_oracle.py --target both` — успешно, повторный запуск идемпотентен.
2. `TMS_CREDITE_*` видны в `USER_OBJECTS` обеих БД; `YBIRO_CREDIT_*_OLD` на месте.
3. `/UNA.md/orasldev/docs/easycredit` и `/docs/iute` отдают 200.
4. `/UNA.md/orasldev/biro26-credit-admin` — вкладка «Provideri API», «Test conexiune» отвечает.
5. Витрина: при сконфигурированном провайдере доступен флоу preapproved → submit → status; при выключенном — старая кнопка.
6. `curl -I https://nufarul.eminescu.md/login` → `HTTP/2 200`.
7. `sudo systemctl status artgranit` — active.

## 11. Вне рамок

- Автоматическое проведение оплаты/документа по факту одобрения кредита (сейчас — только фиксация статуса).
- Webhook-приём статусов от провайдера (только опрос).
- Новые провайдеры сверх EasyCredit и Iute.
- Перевод остальных модулей проекта с `data/*.json` на Oracle.
